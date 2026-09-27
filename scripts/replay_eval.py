"""Replay evaluation: does Hindsight memory actually make the agent better over time?

The replay plays every claim in the dataset through ClaimLens in date order,
into a fresh memory bank:

  for each day:
      retain investigator outcomes decided on or before this day
      for each claim intimated this day:
          if the claim is in the scored set:
              score it WITHOUT memory   (same model, same prompt, no history)
              score it WITH memory      (same model, same prompt + Hindsight recall)
          retain the claim

So memory only ever knows the past, exactly as in production. The only
difference between the two arms is memory, which is what we want to measure.

Ground truth (`_truth`) is used only for scoring, never shown to the agent.

Usage:
    python scripts/replay_eval.py --sample 70          # all fraud + random genuine claims up to 70 scored
    python scripts/replay_eval.py --all                # score every claim (needs a paid LLM tier)
    python scripts/replay_eval.py --resume             # continue an interrupted run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import logging  # noqa: E402

from claimlens import claims as C  # noqa: E402
from claimlens.agent import Investigator  # noqa: E402
from claimlens.config import settings  # noqa: E402
from claimlens.llm import LLM  # noqa: E402
from claimlens.memory import ClaimMemory  # noqa: E402

OUT = ROOT / "data" / "eval"
THRESHOLD = 61  # refer_to_siu


def pick_scored(claims: list[dict], sample: int | None, seed: int = 7) -> set[str]:
    if sample is None:
        return {c["claim_id"] for c in claims}
    fraud = [c["claim_id"] for c in claims if c["_truth"]["label"] == "fraud"]
    legit = [c["claim_id"] for c in claims if c["_truth"]["label"] != "fraud"]
    rng = random.Random(seed)
    k = max(0, min(len(legit), sample - len(fraud)))
    return set(fraud) | set(rng.sample(legit, k))


def metrics(rows: list[dict], arm: str) -> dict:
    tp = sum(r[arm] >= THRESHOLD and r["label"] == "fraud" for r in rows)
    fp = sum(r[arm] >= THRESHOLD and r["label"] != "fraud" for r in rows)
    fn = sum(r[arm] < THRESHOLD and r["label"] == "fraud" for r in rows)
    p = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * rc / (p + rc) if p + rc else 0.0
    amt = sum(r["amount"] for r in rows if r[arm] >= THRESHOLD and r["label"] == "fraud")
    return {"precision": round(p, 3), "recall": round(rc, 3), "f1": round(f1, 3), "tp": tp, "fp": fp, "fn": fn,
            "flagged": tp + fp, "fraud_amount_caught": amt, "auc": round(auc(rows, arm), 3)}


def auc(rows: list[dict], arm: str) -> float:
    pos = [r[arm] for r in rows if r["label"] == "fraud"]
    neg = [r[arm] for r in rows if r["label"] != "fraud"]
    if not pos or not neg:
        return 0.0
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def windows(rows: list[dict]) -> list[dict]:
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by[r["date"][:7]].append(r)
    out = []
    for month in sorted(by):
        rs = by[month]
        fraud = [r for r in rs if r["label"] == "fraud"]
        legit = [r for r in rs if r["label"] != "fraud"]
        rec = lambda arm: (sum(r[arm] >= THRESHOLD for r in fraud) / len(fraud)) if fraud else None  # noqa: E731
        out.append({
            "label": datetime.strptime(month, "%Y-%m").strftime("%b"),
            "n": len(rs), "fraud": len(fraud),
            "with_memory_recall": rec("with_memory"), "stateless_recall": rec("stateless"),
            "with_memory_fp": sum(r["with_memory"] >= THRESHOLD for r in legit),
            "stateless_fp": sum(r["stateless"] >= THRESHOLD for r in legit),
        })
    return out


def _pct(x: float | None) -> str:
    return "" if x is None else f"{x:.0%}"


def write_outputs(rows: list[dict], meta: dict) -> dict:
    res = {
        **meta,
        "threshold": THRESHOLD,
        "n_scored": len(rows),
        "summary": {"with_memory": metrics(rows, "with_memory"), "stateless": metrics(rows, "stateless"),
                    "fraud_amount_total": sum(r["amount"] for r in rows if r["label"] == "fraud")},
        "windows": windows(rows),
        "by_ring": {
            ring: {"n": len(rs), "caught_with_memory": sum(r["with_memory"] >= THRESHOLD for r in rs),
                   "caught_stateless": sum(r["stateless"] >= THRESHOLD for r in rs)}
            for ring in sorted({r["ring"] for r in rows if r["ring"]})
            for rs in [[r for r in rows if r["ring"] == ring]]
        },
        "per_claim": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(res, indent=1))
    s, m = res["summary"]["stateless"], res["summary"]["with_memory"]
    md = [
        f"# ClaimLens replay evaluation ({res['mode']})",
        "",
        f"- Claims replayed: {res['n_total']} (scored: {res['n_scored']}), model `{res['model']}`, flag threshold {THRESHOLD}",
        "",
        "| | Without memory | With Hindsight |",
        "|---|---|---|",
        f"| Fraud recall | {s['recall']:.0%} ({s['tp']}/{s['tp'] + s['fn']}) | {m['recall']:.0%} ({m['tp']}/{m['tp'] + m['fn']}) |",
        f"| Precision | {s['precision']:.0%} | {m['precision']:.0%} |",
        f"| Genuine claims flagged | {s['fp']} | {m['fp']} |",
        f"| ROC AUC | {s['auc']:.2f} | {m['auc']:.2f} |",
        f"| Fraud value flagged | Rs {s['fraud_amount_caught']:,} | Rs {m['fraud_amount_caught']:,} |",
        "",
        "## By fraud ring",
        "",
        "| Ring | Claims | Caught without memory | Caught with memory |",
        "|---|---|---|---|",
        *[f"| {k} | {v['n']} | {v['caught_stateless']} | {v['caught_with_memory']} |" for k, v in res["by_ring"].items()],
        "",
        "## By month",
        "",
        "| Month | Scored | Fraud | Recall without | Recall with | False flags without | False flags with |",
        "|---|---|---|---|---|---|---|",
        *[f"| {w['label']} | {w['n']} | {w['fraud']} | {_pct(w['stateless_recall'])} | "
          f"{_pct(w['with_memory_recall'])} | {w['stateless_fp']} | {w['with_memory_fp']} |"
          for w in res["windows"]],
    ]
    (OUT / "results.md").write_text("\n".join(md) + "\n")
    try:
        chart(res)
    except Exception as e:  # matplotlib optional
        print("chart skipped:", e)
    return res


def chart(res: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ws = [w for w in res["windows"] if w["fraud"]]
    x = [w["label"] for w in ws]
    fig, ax = plt.subplots(figsize=(8, 4), dpi=160)
    ax.plot(x, [100 * (w["stateless_recall"] or 0) for w in ws], "--o", color="#9ca3af", label="Without memory")
    ax.plot(x, [100 * (w["with_memory_recall"] or 0) for w in ws], "-o", color="#6d28d9", lw=2.5, label="With Hindsight memory")
    ax.set_ylabel("Fraud claims flagged (%)")
    ax.set_ylim(-5, 105)
    ax.set_title("Same model, same prompt. The only difference is memory.")
    ax.grid(axis="y", alpha=0.3)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "learning_curve.png")


async def score_pair(agent: Investigator, c: dict) -> tuple[dict, dict, dict]:
    """Score one claim with and without memory, guaranteeing both arms used the SAME model.

    If rate limits pushed one arm onto a backup model, the other arm is re-scored
    on that same model, so the comparison is always like-for-like."""
    (mem_a, ev), base = await asyncio.gather(agent.assess_with_memory(c), agent.assess_stateless(c))
    if mem_a["model"] != base["model"]:
        pinned = Investigator(agent.memory, LLM(model=mem_a["model"], fallback_model=""), strict=True)
        print(f"      (arms used different models; re-scoring baseline on {mem_a['model']})", flush=True)
        base = await pinned.assess_stateless(c)
    return mem_a, ev, base


async def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="      %(message)s")
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--sample", type=int, default=70, help="score all fraud claims + random genuine claims up to N")
    g.add_argument("--all", action="store_true", help="score every claim")
    ap.add_argument("--bank", default=None, help="bank id (default: fresh claimlens-eval-<timestamp>)")
    ap.add_argument("--resume", action="store_true", help="reuse the bank and cached scores from the last run")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--pace", type=float, default=0.0,
                    help="seconds to pause after each scored claim (free LLM tiers: try 8)")
    args = ap.parse_args()

    if not settings.fake_memory and not settings.hindsight_api_key:
        sys.exit("HINDSIGHT_API_KEY is not set.")
    if not settings.fake_llm and not settings.llm_api_key:
        sys.exit("LLM_API_KEY / GROQ_API_KEY is not set.")

    OUT.mkdir(parents=True, exist_ok=True)
    state_file = OUT / "run_state.json"
    cache_file = OUT / "scores.jsonl"
    if args.resume and state_file.exists():
        state = json.loads(state_file.read_text())
    else:
        state = {"bank": args.bank or f"claimlens-eval-{datetime.now():%Y%m%d%H%M}", "retained": [], "verdicts": []}
        cache_file.unlink(missing_ok=True)
    cache = {}
    if cache_file.exists():
        for line in cache_file.read_text().splitlines():
            r = json.loads(line)
            cache[r["claim_id"]] = r

    repo = C.repo()
    claims = sorted(repo.all(), key=lambda c: (c["intimation_date"], c["claim_id"]))
    scored = pick_scored(claims, None if args.all else args.sample)
    mem = ClaimMemory(bank_id=state["bank"])
    # strict: a claim is scored by the language model or not at all. The
    # deterministic fallback would contaminate a with/without comparison.
    agent = Investigator(mem, LLM(), strict=True)
    print(f"Bank {state['bank']}: replaying {len(claims)} claims, scoring {len(scored)}")
    if not args.resume:
        await mem.setup_bank(with_playbook=False)

    verdict_queue = sorted(
        [(c["verdict"]["closed_on"], c) for c in claims if c.get("verdict")], key=lambda x: x[0])
    retained, verdicted = set(state["retained"]), set(state["verdicts"])
    pending: list[dict] = []
    pending_ids: list[tuple[str, str]] = []

    async def flush():
        for i in range(0, len(pending), args.batch):
            await mem.retain_items(pending[i:i + args.batch], "Replay retain")
        for kind, cid in pending_ids:
            (retained if kind == "claim" else verdicted).add(cid)
        pending.clear()
        pending_ids.clear()
        state["retained"], state["verdicts"] = sorted(retained), sorted(verdicted)
        state_file.write_text(json.dumps(state))

    t0 = time.time()
    rows: list[dict] = []
    for n, c in enumerate(claims, 1):
        today = c["intimation_date"]
        # outcomes decided up to today become memory
        while verdict_queue and verdict_queue[0][0] <= today:
            _, vc = verdict_queue.pop(0)
            if vc["claim_id"] not in verdicted:
                pending.append(ClaimMemory.verdict_item(vc, vc["verdict"]))
                pending_ids.append(("verdict", vc["claim_id"]))
        cid = c["claim_id"]
        if cid in scored:
            if cid in cache:
                row = cache[cid]
            else:
                if pending:
                    print(f"      retaining {len(pending)} items into memory before {cid} ...", flush=True)
                await flush()  # memory must hold everything before this claim
                mem_a, ev, base = await score_pair(agent, c)
                t = c["_truth"]
                row = {"claim_id": cid, "date": today, "label": t["label"], "ring": t["ring"],
                       "amount": c["claimed_amount"], "line": c["line"],
                       "with_memory": mem_a["risk_score"], "stateless": base["risk_score"],
                       "with_memory_model": mem_a["model"], "stateless_model": base["model"],
                       "links": len(ev["ranked"]),
                       "top_flags": [f["title"] for f in mem_a["red_flags"][:3]]}
                with cache_file.open("a") as f:
                    f.write(json.dumps(row) + "\n")
                if args.pace:
                    await asyncio.sleep(args.pace)
                mark = "FRAUD" if t["label"] == "fraud" else "     "
                model_tag = "" if mem_a["model"] == agent.llm.model else f"  [{mem_a['model']}]"
                print(f"[{n:3d}/{len(claims)}] {cid} {today} {mark} {t['ring'] or '  '}  "
                      f"without={base['risk_score']:3d}  with={mem_a['risk_score']:3d}  links={row['links']:2d}  "
                      f"({time.time() - t0:,.0f}s){model_tag}", flush=True)
            rows.append(row)
        if cid not in retained:
            pending.append(ClaimMemory.claim_item(c))
            pending_ids.append(("claim", cid))
    await flush()

    mode = "offline-standin" if (settings.fake_memory or settings.fake_llm) else "hindsight"
    res = write_outputs(rows, {"mode": mode, "model": agent.llm.model, "bank": state["bank"],
                               "n_total": len(claims), "generated_at": datetime.now().isoformat(timespec="seconds"),
                               "llm_usage": agent.llm.usage})
    print()
    print((OUT / "results.md").read_text())
    print(f"Wrote {OUT / 'results.json'} and learning_curve.png")


if __name__ == "__main__":
    asyncio.run(main())
