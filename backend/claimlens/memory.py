"""Hindsight memory layer for ClaimLens.

Everything ClaimLens knows about the past lives in one Hindsight memory bank:

* every claim, retained at intake (``timestamp`` = intimation date,
  ``document_id`` = claim id, hard identifiers as ``entities`` and ``tags``)
* every investigator outcome, retained at closure as its own document
* the bank's reflect mission + directives, which encode SIU rules of evidence
* a mental model, "SIU fraud playbook", that Hindsight keeps up to date as
  verdicts accumulate - the agent's learned knowledge, readable by humans

Every call is timed and logged so the UI can show memory working live.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from . import claims as C
from .config import settings

# --------------------------------------------------------------------------- #
# Bank identity                                                                #
# --------------------------------------------------------------------------- #

RETAIN_MISSION = (
    "You are building the long-term memory of an insurance Special Investigation Unit (SIU). "
    "From each claim file or investigator outcome, extract self-contained facts that keep the claim ID "
    "attached. Always capture, exactly as written: claim ID, claimant name, phone number, address, payee "
    "bank account, vehicle registration, garage, surveyor, hospital, treating doctor, intermediary agent code, "
    "police station, policy start date, incident and intimation dates, admission and discharge dates, amounts, "
    "the damage or diagnosis, how the claimant describes the incident, and any investigator decision with its reasons."
)

REFLECT_MISSION = (
    "You are ClaimLens, the institutional memory of an insurance Special Investigation Unit in Hyderabad. "
    "Your job is to connect a new claim to everything the unit has seen before: shared people, phone numbers, "
    "bank accounts, vehicles, addresses, garages, surveyors, hospitals, doctors and agents; repeated stories; "
    "and patterns investigators have already confirmed or cleared. You brief investigators precisely and cite "
    "claim IDs for every connection you make."
)

DIRECTIVES = [
    ("Evidence, not verdicts",
     "A pattern in history is a lead for investigation, never proof. Recommend verification steps; never "
     "state that a claimant is guilty or recommend repudiation on memory alone.", 10),
    ("Cite claim IDs",
     "Every connection to past claims must cite the specific claim IDs it is based on. If you cannot cite a "
     "claim ID, say the connection is unconfirmed.", 9),
    ("Volume is not fraud",
     "High claim volume at a garage, hospital or agent is not suspicious by itself; authorised dealers and large "
     "hospitals legitimately see many claims. Weigh combinations: the same provider AND the same surveyor, shared "
     "personal identifiers across different claimants, near-identical narratives, very early claims after policy "
     "inception, or entities in previously confirmed fraud.", 8),
    ("Respect cleared outcomes",
     "If investigators previously cleared a similar claim or entity as genuine, say so explicitly and lower "
     "suspicion accordingly.", 7),
]

PLAYBOOK_ID = "siu-fraud-playbook"
PLAYBOOK_QUERY = (
    "What fraud patterns have SIU investigators confirmed so far? For each pattern: the modus operandi, the exact "
    "entities involved (garages, surveyors, hospitals, doctors, agent codes, phone numbers, payee accounts, vehicles, "
    "addresses), the claim IDs, and the tell-tale signs that separate it from genuine claims. Also list entities "
    "that look busy but were cleared as genuine."
)

# --------------------------------------------------------------------------- #
# Operation log (feeds the Memory Inspector in the UI)                         #
# --------------------------------------------------------------------------- #


@dataclass
class MemoryOp:
    op: str                     # retain | recall | reflect | mental_model | setup
    label: str                  # short human description
    detail: dict[str, Any] = field(default_factory=dict)
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    ms: int = 0
    hits: int | None = None
    ok: bool = True
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class OpLog:
    def __init__(self, maxlen: int = 300):
        self._ops: deque[MemoryOp] = deque(maxlen=maxlen)

    def add(self, op: MemoryOp) -> None:
        self._ops.append(op)

    def recent(self, n: int = 80) -> list[dict]:
        return [o.to_dict() for o in list(self._ops)[-n:]][::-1]


oplog = OpLog()


class _timed:
    """Context manager that times a memory op and records success/failure."""

    def __init__(self, op: MemoryOp, sink: list[MemoryOp] | None):
        self.op, self.sink = op, sink

    async def __aenter__(self):
        self.t0 = time.perf_counter()
        return self.op

    async def __aexit__(self, exc_type, exc, tb):
        self.op.ms = int((time.perf_counter() - self.t0) * 1000)
        if exc is not None:
            self.op.ok = False
            self.op.error = f"{type(exc).__name__}: {str(exc)[:200]}"
        oplog.add(self.op)
        if self.sink is not None:
            self.sink.append(self.op)
        return False  # never swallow


# --------------------------------------------------------------------------- #
# Result normalisation                                                         #
# --------------------------------------------------------------------------- #


def _get(o: Any, name: str, default: Any = None) -> Any:
    if isinstance(o, dict):
        return o.get(name, default)
    return getattr(o, name, default)


def fact_dict(r: Any) -> dict:
    return {
        "id": _get(r, "id"),
        "text": _get(r, "text", ""),
        "type": _get(r, "type"),
        "document_id": _get(r, "document_id"),
        "tags": list(_get(r, "tags") or []),
        "entities": list(_get(r, "entities") or []),
        "occurred_start": _get(r, "occurred_start"),
        "metadata": dict(_get(r, "metadata") or {}),
        "rerank": _score(r, "reranker"),
    }


def _score(r: Any, stage: str) -> float | None:
    sc = _get(r, "scores")
    v = _get(sc, stage) if sc is not None else None
    return float(v) if isinstance(v, (int, float)) else None


def claim_id_of(fact: dict) -> str | None:
    """Map a recalled fact back to the claim it came from."""
    md = fact.get("metadata") or {}
    if md.get("claim_id"):
        return md["claim_id"]
    doc = fact.get("document_id") or ""
    if doc.startswith("verdict:"):
        return doc.split(":", 1)[1]
    if doc.startswith("CLM-"):
        return doc
    return None


# --------------------------------------------------------------------------- #
# Memory facade                                                                #
# --------------------------------------------------------------------------- #


def make_client():
    if settings.fake_memory:
        from .fake_hindsight import FakeHindsight

        return FakeHindsight()
    from hindsight_client import Hindsight

    return Hindsight(base_url=settings.hindsight_url, api_key=settings.hindsight_api_key, timeout=180.0)


class ClaimMemory:
    def __init__(self, client=None, bank_id: str | None = None):
        self.client = client or make_client()
        self.bank_id = bank_id or settings.bank_id

    # ---- setup ------------------------------------------------------------
    async def setup_bank(self, *, with_playbook: bool = True) -> list[str]:
        """Create/configure the bank. Idempotent."""
        done: list[str] = []
        async with _timed(MemoryOp("setup", "Create memory bank", {"bank": self.bank_id}), None):
            await self.client.acreate_bank(
                self.bank_id,
                reflect_mission=REFLECT_MISSION,
                retain_mission=RETAIN_MISSION,
                enable_observations=True,
                background="Special Investigation Unit, motor and health claims, Hyderabad region.",
            )
        done.append("bank")
        try:
            await self.client.aupdate_bank_config(
                self.bank_id,
                disposition_skepticism=4,   # investigators should be sceptical...
                disposition_literalism=4,   # ...precise about identifiers...
                disposition_empathy=2,      # ...but not dismissive of genuine claimants
                observations_mission=(
                    "Consolidate recurring patterns across claims: entities that appear in several claims, "
                    "shared identifiers across different claimants, repeated narratives, and what investigators "
                    "concluded about them."
                ),
            )
            done.append("disposition")
        except Exception:  # older servers: disposition via create_bank is enough
            pass

        existing = {(_get(d, "name") or "") for d in await self._list_directives()}
        for name, content, prio in DIRECTIVES:
            if name in existing:
                continue
            async with _timed(MemoryOp("setup", f"Directive: {name}"), None):
                await self.client.acreate_directive(self.bank_id, name=name, content=content, priority=prio)
            done.append(f"directive:{name}")

        if with_playbook:
            try:
                await self.client.aget_mental_model(self.bank_id, PLAYBOOK_ID)
            except Exception:
                async with _timed(MemoryOp("mental_model", "Create SIU fraud playbook"), None):
                    await self.client.acreate_mental_model(
                        self.bank_id, name="SIU fraud playbook", source_query=PLAYBOOK_QUERY,
                        id=PLAYBOOK_ID, max_tokens=1800,
                        trigger={"refresh_after_consolidation": True},
                    )
                done.append("mental_model")
        return done

    async def _list_directives(self) -> list:
        try:
            res = await self.client.alist_directives(self.bank_id)
        except Exception:
            return []
        items = _get(res, "items", None)
        if items is None and isinstance(res, list):
            items = res
        return list(items or [])

    async def reset(self) -> None:
        try:
            await self.client.adelete_bank(self.bank_id)
        except Exception:
            pass

    # ---- retain -----------------------------------------------------------
    @staticmethod
    def claim_item(claim: dict) -> dict:
        ents = C.entities(claim)
        return {
            "content": C.render(claim),
            "timestamp": C.as_datetime(claim["intimation_date"]),
            "context": f"{claim['line']} insurance claim file received at intake",
            "document_id": claim["claim_id"],
            "metadata": {"claim_id": claim["claim_id"], "kind": "claim", "line": claim["line"]},
            "entities": [{"text": e.label, "type": e.kind} for e in ents],
            "tags": ["claim", f"line:{claim['line']}", *[e.tag for e in ents]],
            "update_mode": "replace",
        }

    @staticmethod
    def verdict_item(claim: dict, verdict: dict) -> dict:
        ents = C.entities(claim)
        closed = verdict.get("closed_on") or claim["intimation_date"]
        return {
            "content": C.render_verdict(claim, verdict),
            "timestamp": C.as_datetime(closed),
            "context": "SIU investigator outcome for a claim",
            "document_id": f"verdict:{claim['claim_id']}",
            "metadata": {"claim_id": claim["claim_id"], "kind": "verdict", "decision": verdict["decision"]},
            "entities": [{"text": e.label, "type": e.kind} for e in ents],
            "tags": ["verdict", f"decision:{verdict['decision']}", f"line:{claim['line']}", *[e.tag for e in ents]],
            "update_mode": "replace",
        }

    async def retain_items(self, items: list[dict], label: str, *, sink=None, retain_async: bool = False) -> None:
        # document_id and update_mode are per-item in the batch API
        async with _timed(MemoryOp("retain", label, {"items": len(items),
                                                     "documents": [i["document_id"] for i in items][:12]}), sink) as op:
            await self.client.aretain_batch(self.bank_id, items=items, retain_async=retain_async)
            op.hits = len(items)

    async def retain_claim(self, claim: dict, *, sink=None) -> None:
        await self.retain_items([self.claim_item(claim)], f"Retain claim {claim['claim_id']}", sink=sink)

    async def retain_verdict(self, claim: dict, verdict: dict, *, sink=None) -> None:
        await self.retain_items([self.verdict_item(claim, verdict)],
                                f"Retain outcome for {claim['claim_id']}: {verdict['decision']}", sink=sink)

    # ---- recall -----------------------------------------------------------
    async def recall(self, query: str, *, label: str, sink=None, tags: list[str] | None = None,
                     tags_match: str = "any", types: list[str] | None = None, budget: str = "low",
                     max_tokens: int = 1500, query_timestamp: str | None = None,
                     temporal_window: dict | None = None, min_scores: dict | None = None) -> list[dict]:
        detail = {"query": query[:160], "tags": tags, "types": types, "budget": budget}
        async with _timed(MemoryOp("recall", label, detail), sink) as op:
            kwargs: dict[str, Any] = dict(query=query, budget=budget, max_tokens=max_tokens)
            if tags:
                kwargs.update(tags=tags, tags_match=tags_match)
            if types:
                kwargs["types"] = types
            if query_timestamp:
                kwargs["query_timestamp"] = query_timestamp
            if temporal_window:
                kwargs["temporal_window"] = temporal_window
            if min_scores:
                kwargs["min_scores"] = min_scores
            res = await self.client.arecall(self.bank_id, **kwargs)
            facts = [fact_dict(r) for r in (_get(res, "results") or [])]
            op.hits = len(facts)
            return facts

    # ---- reflect ----------------------------------------------------------
    async def reflect(self, query: str, *, label: str, context: str | None = None, budget: str = "mid",
                      sink=None, response_schema: dict | None = None) -> dict:
        async with _timed(MemoryOp("reflect", label, {"query": query[:160], "budget": budget}), sink) as op:
            kwargs: dict[str, Any] = dict(query=query, budget=budget, include_facts=True)
            if context:
                kwargs["context"] = context
            if response_schema:
                kwargs["response_schema"] = response_schema
            res = await self.client.areflect(self.bank_id, **kwargs)
            based = _get(res, "based_on")
            mems = [fact_dict(m) for m in (_get(based, "memories") or [])] if based else []
            op.hits = len(mems)
            return {
                "text": _get(res, "text", ""),
                "structured": _get(res, "structured_output"),
                "memories": mems,
                "directives": [_get(d, "name") for d in (_get(based, "directives") or [])] if based else [],
            }

    # ---- mental model -----------------------------------------------------
    async def playbook(self) -> dict:
        async with _timed(MemoryOp("mental_model", "Read SIU fraud playbook"), None):
            mm = await self.client.aget_mental_model(self.bank_id, PLAYBOOK_ID, detail="full")
        return {
            "name": _get(mm, "name"),
            "content": _get(mm, "content") or "",
            "last_refreshed_at": _get(mm, "last_refreshed_at"),
            "is_stale": _get(mm, "is_stale"),
        }

    async def refresh_playbook(self) -> None:
        async with _timed(MemoryOp("mental_model", "Refresh SIU fraud playbook"), None):
            await self.client.arefresh_mental_model(self.bank_id, PLAYBOOK_ID)

    async def stats(self) -> dict:
        out: dict[str, Any] = {"bank_id": self.bank_id}
        for t in ("world", "experience", "observation"):
            try:
                res = await self.client.alist_memories(self.bank_id, type=t, limit=1)
                out[t] = _get(res, "total", 0)
            except Exception:
                out[t] = None
        return out


# --------------------------------------------------------------------------- #
# Investigation probes                                                         #
# --------------------------------------------------------------------------- #


@dataclass
class Probe:
    """One targeted question the agent asks memory about a new claim."""

    reason: str                 # key into claims.KIND_LABEL
    label: str
    query: str
    tags: list[str] | None = None
    types: list[str] | None = None
    budget: str = "low"
    max_tokens: int = 1200
    temporal_window: dict | None = None
    min_scores: dict | None = None
    entity: C.Entity | None = None


def plan_probes(claim: dict) -> list[Probe]:
    """Decide what to ask memory. Each hard identifier gets its own tag-scoped
    recall (exact linking); the narrative gets a semantic recall (catches
    templated stories across different people); a pattern recall pulls the
    consolidated observations; a time-windowed recall looks at recent activity."""
    probes: list[Probe] = []
    for e in C.entities(claim):
        probes.append(Probe(
            reason=e.kind, entity=e,
            label=f"Who else has {e.label}?",
            query=f"Past claims and investigator outcomes involving {e.label}",
            tags=[e.tag],
        ))
    probes.append(Probe(
        reason="narrative", label="Have we heard this story before?",
        query=f"{claim['line']} claim where: {claim['narrative']}",
        tags=[f"line:{claim['line']}"], budget="mid", max_tokens=2000,
        # Semantic search always returns *something*; only a genuinely close
        # retelling should count as "we've heard this story before".
        min_scores={"reranker": settings.narrative_min_rerank},
    ))
    probes.append(Probe(
        reason="pattern", label="Does this match a confirmed pattern?",
        query=f"Confirmed fraud patterns or cleared look-alikes relevant to a {C.summary(claim)}",
        types=["observation"], budget="mid", max_tokens=1500,
    ))
    end = C.as_datetime(claim["intimation_date"])
    probes.append(Probe(
        reason="timeline", label="What happened around this time?",
        query=f"Similar {claim['line']} claims in the weeks before {claim['intimation_date']}: {C.summary(claim)}",
        tags=[f"line:{claim['line']}"], budget="low", max_tokens=1200,
        temporal_window={"start": (end - timedelta(days=90)).isoformat(), "end": end.isoformat()},
    ))
    return probes


@dataclass
class Link:
    claim_id: str
    reasons: set[str] = field(default_factory=set)
    facts: list[str] = field(default_factory=list)
    verdict_facts: list[str] = field(default_factory=list)


async def gather_evidence(mem: ClaimMemory, claim: dict, *, sink: list[MemoryOp] | None = None,
                          exclude: set[str] | None = None, concurrency: int = 6) -> dict:
    """Run every probe concurrently and fold the results into linked claims."""
    exclude = (exclude or set()) | {claim["claim_id"]}
    probes = plan_probes(claim)
    sem = asyncio.Semaphore(concurrency)

    async def run(p: Probe):
        async with sem:
            try:
                return p, await mem.recall(
                    p.query, label=p.label, sink=sink, tags=p.tags,
                    tags_match="any_strict" if p.tags else "any", types=p.types, budget=p.budget,
                    max_tokens=p.max_tokens, query_timestamp=C.as_datetime(claim["intimation_date"]).isoformat(),
                    temporal_window=p.temporal_window, min_scores=p.min_scores,
                )
            except Exception:
                return p, []  # one failed probe must not sink the investigation

    results = await asyncio.gather(*(run(p) for p in probes))

    links: dict[str, Link] = {}
    insights: list[str] = []
    probe_summary = []
    for p, facts in results:
        linked_here = set()
        for f in facts:
            cid = claim_id_of(f)
            if cid is None:
                if f.get("type") == "observation" and f["text"] not in insights:
                    insights.append(f["text"])
                continue
            if cid in exclude:
                continue
            ln = links.setdefault(cid, Link(cid))
            # Tag-scoped probes are exact matches. Semantic probes only count
            # as a link reason if they are the narrative / timeline probe.
            ln.reasons.add(p.reason)
            linked_here.add(cid)
            bucket = ln.verdict_facts if (f.get("document_id") or "").startswith("verdict:") else ln.facts
            if f["text"] not in bucket and len(bucket) < 6:
                bucket.append(f["text"])
        probe_summary.append({"reason": p.reason, "label": p.label, "hits": len(facts),
                              "linked_claims": sorted(linked_here),
                              "entity": p.entity.label if p.entity else None})
    return {"links": links, "insights": insights[:8], "probes": probe_summary}
