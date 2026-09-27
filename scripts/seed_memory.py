"""Create and configure the ClaimLens memory bank, then load claims history into Hindsight.

History is replayed in the order events really happened: each claim is retained
with its intimation date, each investigator outcome with its closing date. The
September claims are left out; they are the live review queue.

Usage:
    python scripts/seed_memory.py            # configure bank + load history
    python scripts/seed_memory.py --reset    # delete the bank first
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from claimlens import claims as C  # noqa: E402
from claimlens.config import settings  # noqa: E402
from claimlens.memory import ClaimMemory  # noqa: E402


def history_events(repo: C.ClaimRepo) -> list[tuple[str, dict]]:
    events: list[tuple[str, int, dict]] = []
    for c in repo.history():
        events.append((c["intimation_date"], 0, ClaimMemory.claim_item(c)))
        if c.get("verdict"):
            events.append((c["verdict"]["closed_on"], 1, ClaimMemory.verdict_item(c, c["verdict"])))
    events.sort(key=lambda e: (e[0], e[1]))
    return [(d, item) for d, _, item in events]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="delete the bank before seeding")
    ap.add_argument("--batch", type=int, default=8, help="items per retain call")
    ap.add_argument("--bank", default=settings.bank_id)
    args = ap.parse_args()

    if not settings.fake_memory and not settings.hindsight_api_key:
        sys.exit("HINDSIGHT_API_KEY is not set. Copy .env.example to .env and fill it in.")

    repo = C.repo()
    mem = ClaimMemory(bank_id=args.bank)
    if args.reset:
        print(f"Deleting bank {args.bank} ...")
        await mem.reset()
    print(f"Configuring bank {args.bank} (mission, disposition, directives, playbook) ...")
    print("  ", ", ".join(await mem.setup_bank()))

    events = history_events(repo)
    print(f"Retaining {len(events)} history events ({len(repo.history())} claims + outcomes) "
          f"in batches of {args.batch} ...")
    t0 = time.time()
    for i in range(0, len(events), args.batch):
        chunk = [item for _, item in events[i:i + args.batch]]
        for attempt in range(4):
            try:
                await mem.retain_items(chunk, f"Seed history {i + 1}-{i + len(chunk)}")
                break
            except Exception as e:  # transient network / capacity errors
                wait = 5 * (attempt + 1)
                print(f"   retain failed ({e}); retrying in {wait}s")
                await asyncio.sleep(wait)
        else:
            sys.exit("Giving up after repeated retain failures.")
        done = min(i + args.batch, len(events))
        rate = done / max(time.time() - t0, 1e-6)
        eta = (len(events) - done) / max(rate, 1e-6)
        print(f"   {done:4d}/{len(events)}  through {events[done - 1][0]}  ~{eta:,.0f}s left", flush=True)

    print("Asking Hindsight to (re)build the SIU fraud playbook mental model ...")
    try:
        await mem.refresh_playbook()
    except Exception as e:
        print(f"   playbook refresh deferred: {e}")
    print("Memory stats:", await mem.stats())
    print(f"Done in {time.time() - t0:,.0f}s. Start the app: uvicorn claimlens.api:app --app-dir backend")


if __name__ == "__main__":
    asyncio.run(main())
