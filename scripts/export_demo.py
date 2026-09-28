"""Export a recorded run of ClaimLens into a static site bundle.

Run this AFTER you've done the live demo (investigate #10595, confirm fraud,
#10606, #10614, #10597, generate the briefing on #10595) with the server still
running. It copies the real results into frontend/public/demo/, which the
GitHub Pages build replays. No keys are exported: only what the UI already shows.

    python scripts/export_demo.py                  # server on http://localhost:8000
    python scripts/export_demo.py --url http://127.0.0.1:8000
    python scripts/export_demo.py --skip-asks      # don't spend LLM calls on the 4 suggested questions
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "demo"

DEMO_CLAIMS = ["CLM-2026-10595", "CLM-2026-10606", "CLM-2026-10614", "CLM-2026-10597"]
ASKS = [
    "Which surveyors appear most often in claims we later repudiated?",
    "Is Lakshmi Hyundai, Kondapur a fraud risk?",
    "What do the Lifeline Multispeciality claims have in common?",
    "Has vehicle TS08FK4521 been claimed before?",
]
# never publish anything that looks like a secret
SECRET_KEYS = {"api_key", "hindsight_api_key", "groq_api_key", "authorization", "token"}


def call(base: str, path: str, body: dict | None = None, timeout: int = 180):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        base + path, data=data, method="POST" if body is not None else "GET",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def scrub(x):
    if isinstance(x, dict):
        return {k: ("[removed]" if k.lower() in SECRET_KEYS else scrub(v)) for k, v in x.items()}
    if isinstance(x, list):
        return [scrub(v) for v in x]
    return x


def write(name: str, obj) -> None:
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(scrub(obj), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--skip-asks", action="store_true")
    a = ap.parse_args()
    base = a.url.rstrip("/")

    try:
        status = call(base, "/api/status")
    except (urllib.error.URLError, OSError) as e:
        print(f"Can't reach the ClaimLens server at {base} ({e}).")
        print("Start it first:  uvicorn claimlens.api:app --app-dir backend --port 8000")
        return 1

    if status.get("memory_backend") != "hindsight":
        print("WARNING: the server is using the offline stand-in, not Hindsight. "
              "The exported demo would not be the real system.")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    status["recorded_at"] = datetime.now().strftime("%d %b %Y")
    status.pop("hindsight_url", None)
    write("status.json", status)

    queue = call(base, "/api/claims?scope=queue")
    history = call(base, "/api/claims?scope=history")
    write("queue.json", queue)
    write("history.json", history)
    print(f"queue {len(queue)} claims, history {len(history)} claims")

    ids = [r["claim_id"] for r in queue] + [r["claim_id"] for r in history]
    details = {}
    for i, cid in enumerate(ids, 1):
        d = call(base, f"/api/claims/{cid}")
        details[cid] = d
        write(f"claims/{cid}.json", d)
        if i % 50 == 0:
            print(f"  exported {i}/{len(ids)} claims")
    print(f"exported {len(ids)} claim files")

    ev = call(base, "/api/eval")
    if not ev.get("available"):
        print("WARNING: no replay results (data/eval/results.json). The 'Does memory help?' page will be empty.")
    write("eval.json", ev)
    write("ops.json", call(base, "/api/memory/ops?n=300"))
    try:
        write("playbook.json", call(base, "/api/memory/playbook"))
    except urllib.error.HTTPError as e:
        print(f"WARNING: playbook not exported ({e}). Click Playbook → Refresh in the app, then re-run.")
        write("playbook.json", {"name": "SIU fraud playbook", "content": "Not recorded.", "last_refreshed_at": None, "is_stale": None})

    asks = {}
    if not a.skip_asks:
        for q in ASKS:
            print(f"asking memory: {q}")
            try:
                asks[q] = call(base, "/api/ask", {"question": q}, timeout=300)
            except urllib.error.HTTPError as e:
                print(f"  skipped ({e})")
    write("asks.json", asks)

    # sanity checks: the guided demo needs these
    problems = []
    for cid in DEMO_CLAIMS:
        d = details.get(cid)
        if not d or not d.get("investigation"):
            problems.append(f"{cid} has no investigation. Open it and click Investigate with memory.")
        elif d["investigation"].get("with_memory", {}).get("model", "").startswith("fallback"):
            problems.append(f"{cid} was scored by the fallback (rate limit). Re-investigate it.")
    d = details.get("CLM-2026-10595") or {}
    if (d.get("decision") or {}).get("decision") != "fraud_confirmed":
        problems.append("CLM-2026-10595 isn't marked Confirm fraud. Do that before #10606.")
    if not d.get("briefing"):
        problems.append("CLM-2026-10595 has no briefing. Click Generate briefing (optional but nice).")

    print()
    if problems:
        print("Exported, but fix these for a complete demo and re-run:")
        for p in problems:
            print("  -", p)
    else:
        print("All four demo claims recorded.")
    print(f"Written to {OUT.relative_to(ROOT)}. Next: git add frontend/public/demo && git commit && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
