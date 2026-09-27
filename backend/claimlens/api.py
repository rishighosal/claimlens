"""FastAPI app: the investigator workbench API + static UI."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import claims as C
from .agent import Investigator
from .config import ROOT, settings
from .llm import LLM
from .memory import ClaimMemory, oplog
from .store import Store

log = logging.getLogger("claimlens")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


class Ctx:
    repo: C.ClaimRepo
    memory: ClaimMemory
    llm: LLM
    agent: Investigator
    store: Store


ctx = Ctx()


async def seed_offline_history() -> None:
    """Offline mode only: the stand-in memory lives in RAM, so load history at boot."""
    items = []
    for c in ctx.repo.history():
        items.append(ClaimMemory.claim_item(c))
        if c.get("verdict"):
            items.append(ClaimMemory.verdict_item(c, c["verdict"]))
    await ctx.memory.retain_items(items, f"Load {len(ctx.repo.history())} historical claims (offline)")
    for cid, v in ctx.store.section("decisions").items():
        if (c := ctx.repo.get(cid)) is not None:
            await ctx.memory.retain_verdict(c, v)
    for cid in ctx.store.section("investigations"):
        if (c := ctx.repo.get(cid)) is not None:
            await ctx.memory.retain_claim(c)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx.repo = C.repo()
    ctx.memory = ClaimMemory()
    ctx.llm = LLM()
    ctx.agent = Investigator(ctx.memory, ctx.llm)
    ctx.store = Store(settings.state_path)
    if settings.fake_memory:
        await ctx.memory.setup_bank()
        await seed_offline_history()
    yield


app = FastAPI(title="ClaimLens", version="1.0.0", lifespan=lifespan)

# --------------------------------------------------------------------------- #
# Schemas                                                                      #
# --------------------------------------------------------------------------- #


class DecisionIn(BaseModel):
    decision: Literal["approved", "cleared", "referred", "fraud_confirmed"]
    notes: str = Field("", max_length=2000)
    investigator: str = Field("", max_length=120)


class AskIn(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _need(claim_id: str) -> dict:
    c = ctx.repo.get(claim_id)
    if c is None:
        raise HTTPException(404, f"Unknown claim {claim_id}")
    return c


def _row(c: dict) -> dict:
    inv = ctx.store.get("investigations", c["claim_id"])
    dec = ctx.store.get("decisions", c["claim_id"]) or c.get("verdict")
    return {
        "claim_id": c["claim_id"], "line": c["line"], "intimation_date": c["intimation_date"],
        "claimant": c["claimant"]["name"], "summary": C.summary(c), "claimed_amount": c["claimed_amount"],
        "status": c["status"],
        "risk": inv["with_memory"]["risk_score"] if inv else None,
        "band": inv["with_memory"]["band"] if inv else None,
        "stateless_risk": inv["stateless"]["risk_score"] if inv else None,
        "decision": dec.get("decision") if dec else None,
    }


# --------------------------------------------------------------------------- #
# Routes                                                                       #
# --------------------------------------------------------------------------- #


@app.get("/api/status")
async def status():
    try:
        stats = await ctx.memory.stats()
        reachable = True
    except Exception as e:  # pragma: no cover - network
        stats, reachable = {"error": str(e)[:200]}, False
    return {
        "memory_backend": "offline-standin" if settings.fake_memory else "hindsight",
        "hindsight_url": None if settings.fake_memory else settings.hindsight_url,
        "hindsight_reachable": reachable,
        "bank_id": ctx.memory.bank_id,
        "llm_model": "offline-standin" if settings.fake_llm else ctx.llm.model,
        "llm_usage": ctx.llm.usage,
        "memory_stats": stats,
        "history_claims": len(ctx.repo.history()),
        "queue_claims": len(ctx.repo.open_queue()),
    }


@app.get("/api/claims")
async def list_claims(scope: Literal["queue", "history", "all"] = "queue"):
    src = {"queue": ctx.repo.open_queue, "history": ctx.repo.history, "all": ctx.repo.all}[scope]()
    rows = [_row(c) for c in src]
    rows.sort(key=lambda r: r["intimation_date"], reverse=(scope != "queue"))
    return rows


@app.get("/api/claims/{claim_id}")
async def get_claim(claim_id: str):
    c = _need(claim_id)
    return {
        "claim": C.public(c),
        "rendered": C.render(c),
        "investigation": ctx.store.get("investigations", claim_id),
        "briefing": ctx.store.get("briefings", claim_id),
        "decision": ctx.store.get("decisions", claim_id) or c.get("verdict"),
    }


@app.post("/api/claims/{claim_id}/investigate")
async def investigate(claim_id: str):
    c = _need(claim_id)
    result = await ctx.agent.investigate(c, ctx.repo, decisions=ctx.store.section("decisions"))
    ctx.store.put("investigations", claim_id, result)
    return result


@app.post("/api/claims/{claim_id}/briefing")
async def briefing(claim_id: str):
    c = _need(claim_id)
    try:
        b = await ctx.agent.briefing(c)
    except Exception as e:
        raise HTTPException(502, f"Hindsight reflect failed: {e}") from e
    ctx.store.put("briefings", claim_id, b)
    return b


@app.post("/api/claims/{claim_id}/decision")
async def decide(claim_id: str, body: DecisionIn):
    c = _need(claim_id)
    verdict = {
        "decision": body.decision,
        "notes": body.notes.strip(),
        "investigator": body.investigator.strip() or "SIU desk",
        "closed_on": date.today().isoformat(),
        "paid_amount": c["claimed_amount"] if body.decision in ("approved", "cleared") else 0,
    }
    sink: list = []
    try:
        await ctx.memory.retain_verdict(c, verdict, sink=sink)
    except Exception as e:
        raise HTTPException(502, f"Could not write outcome to Hindsight: {e}") from e
    ctx.store.put("decisions", claim_id, verdict)
    return {"ok": True, "verdict": verdict, "memory_ops": [o.to_dict() for o in sink]}


@app.post("/api/ask")
async def ask(body: AskIn):
    try:
        return await ctx.memory.reflect(body.question, label="Investigator question", budget="mid")
    except Exception as e:
        raise HTTPException(502, f"Hindsight reflect failed: {e}") from e


@app.get("/api/memory/playbook")
async def playbook():
    try:
        return await ctx.memory.playbook()
    except Exception as e:
        raise HTTPException(502, f"Could not read the playbook mental model: {e}") from e


@app.post("/api/memory/playbook/refresh")
async def refresh_playbook():
    try:
        await ctx.memory.refresh_playbook()
    except Exception as e:
        raise HTTPException(502, str(e)) from e
    return {"ok": True}


@app.get("/api/memory/ops")
async def memory_ops(n: int = 80):
    return oplog.recent(n)


@app.get("/api/eval")
async def eval_results():
    p = ROOT / "data" / "eval" / "results.json"
    if not p.exists():
        return {"available": False}
    return {"available": True, **json.loads(p.read_text())}


@app.post("/api/admin/reset-ui")
async def reset_ui():
    ctx.store.clear()
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Static UI                                                                    #
# --------------------------------------------------------------------------- #

DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        f = (DIST / path).resolve()
        if path and f.is_file() and DIST.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
