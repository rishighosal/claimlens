# Demo script (live judging + recorded video)

Target: 3 minutes. The story: *watch the agent get smarter.*

## Before you start (one time, about 20 minutes)

```bash
python scripts/seed_memory.py --reset          # loads Jan-Aug history into Hindsight
python scripts/replay_eval.py --sample 70      # produces the "Does memory help?" page (run once, ~15-30 min)
uvicorn claimlens.api:app --app-dir backend --port 8000
```

- Open the app, click **Playbook** in the memory panel, and hit **Refresh** so the mental model is built before judges see it.
- Pre-run `Investigate` once on a throwaway claim to warm up the API connection. Then `POST /api/admin/reset-ui` (or delete `data/state.json`) so the queue looks fresh.
- Browser zoom 110%, close other tabs, notifications off.

## The 3-minute flow

| Time | Screen | Say |
|---|---|---|
| 0:00 | Queue | "I'm an SIU analyst at a Hyderabad insurer. 26 claims came in this September. Organised fraud never looks suspicious on one claim; it only shows up across history. ClaimLens gives the triage agent that history, using Hindsight as memory." |
| 0:20 | **#10595** (Sri Balaji Auto Works, K. Venkat Rao). Click **Investigate with memory** | "Same model, same prompt, run twice. Watch the memory panel on the right: it's asking Hindsight about the phone, the bank account, the surveyor, the story…" |
| 0:40 | Compare cards | "Without memory: fast-track. A hit-and-run at night, no FIR. Happens every day. With memory: refer to SIU." |
| 0:55 | Red flags + evidence graph | "Here's why, and every point cites a claim ID. The claimant's phone matches #10572, which SIU repudiated in August. The payee bank account matches #10566, repudiated in July. The same surveyor, K. Venkat Rao, handled every one of them, and the story is almost word-for-word what other claimants told us. Red boxes are past claims we confirmed as fraud." Hover the shared-phone node. |
| 1:20 | Type findings, click **Confirm fraud** | "I record the outcome. That's a Hindsight retain: memory just learned something." |
| 1:30 | **#10606** (next R1 claim) → Investigate | "Nine days later, same ring. Now it links straight to the claim I closed a minute ago." Point at #10595 in the evidence. **This is the learning moment.** |
| 1:50 | **#10614** (Sri Balaji garage, surveyor T. Lavanya) → Investigate | "Same garage, but a different surveyor, and the other driver's registration is on record. Memory knows six genuine claims at this garage, all with other surveyors, were paid without issue. It doesn't over-flag. Volume isn't fraud; that's one of the bank's directives." |
| 2:10 | **#10597** (Creta TS08FK4521) → Investigate | "Nobody ever flagged this one. But memory remembers this exact car claiming the exact same front-left damage in February and June, under a different owner." |
| 2:25 | Memory panel → **Ask memory** → "What do the Lifeline Multispeciality claims have in common?" | "Reflect over the whole bank: weekend admissions, same doctor, policies five weeks old, same agent." |
| 2:40 | **Does memory help?** tab | "And we measured it: replaying nine months of claims in date order. Same model with and without memory. [read the two recall numbers]. Each ring's first claims are missed, because there's nothing to remember yet. After that, memory catches them." |
| 2:55 | | "ClaimLens: claims triage that remembers every claim. It recommends; people decide." |

## If something breaks live

- The LLM is rate-limited: the agent retries, falls back to `qwen/qwen3-32b`, then to a deterministic link-strength score (labelled `fallback`). Keep talking.
- Hindsight slow: the investigation shows progress steps; recall budget is `low` for the identifier probes.
- Worst case: the memory panel still shows the recorded retain/recall log from earlier runs, and the eval page is static JSON.

## Screenshots to capture for the article
1. Compare cards on #10595 (without vs with)
2. Evidence graph on #10595 or #10606
3. Memory panel "Live activity" during an investigation (shows retain/recall calls)
4. The Playbook mental model text
5. `data/eval/learning_curve.png`
