# ClaimLens

**Claims triage that remembers every claim it has ever seen.**

Organised insurance fraud is invisible one claim at a time. A staged rear-end collision at a Moosapet garage looks exactly like a genuine one, until you notice that the same surveyor approved five others like it, two "unrelated" claimants share a phone number, and the story is word-for-word what someone else told us in March.

Claims handlers can't hold nine months of history in their heads, and a normal LLM triage bot starts from zero on every claim. ClaimLens is a fraud-triage agent for an insurer's Special Investigation Unit (SIU) that uses [Hindsight](https://github.com/vectorize-io/hindsight) as its institutional memory. Every claim and every investigator outcome goes into memory. Every new claim is checked against all of it.


## What it does

1. **Intake:** a new claim arrives: motor or health, with the claimant, phone, bank account, vehicle, garage, surveyor, hospital, doctor and agent.
2. **Investigate:** ClaimLens asks Hindsight ~10 targeted questions in parallel ("who else used this phone?", "have we heard this story before?", "what did SIU conclude about this surveyor?") and folds the answers into an evidence graph of linked past claims.
3. **Assess twice:** the same model and prompt score the claim **without memory** and **with memory**, side by side. The only difference is Hindsight.
4. **Explain:** every red flag cites the past claim IDs it rests on. Citations the model invents are stripped.
5. **Learn:** when an investigator records an outcome (approved, cleared, referred, fraud confirmed), it is retained. The next claim touching the same people, providers or story is judged with it. A Hindsight mental model, the *SIU fraud playbook*, rewrites itself as outcomes accumulate.

## Why memory is the product (what the demo claims show)

| | Stateless LLM | ClaimLens + Hindsight |
|---|---|---|
| Staged "unknown vehicle hit me from behind" claim | Plausible, no FIR needed for hit-and-run. **Fast-track.** | 3 earlier claims with the same surveyor; claimant's phone matches a claim SIU repudiated in August; narrative near-identical to 4 others. **Refer to SIU.** |
| Busy authorised dealer with 16 claims | n/a | Recognises the volume as normal; investigators cleared them all. **Not flagged.** |
| Same Creta, same front-left damage, new owner | Nothing unusual | Vehicle claimed identical damage in Feb and June. **Refer.** |

The dataset has decoys on purpose (a high-volume but clean dealer, genuine claims at the fraud garage handled by other surveyors), so the agent has to learn *combinations*, not just "this garage is bad".

## How Hindsight is used

All of it lives in [`backend/claimlens/memory.py`](backend/claimlens/memory.py).

| Hindsight feature | How ClaimLens uses it |
|---|---|
| **retain** with `document_id`, `timestamp`, `entities`, `tags`, `metadata` | Each claim is retained at intake (timestamp = intimation date). Each investigator outcome is retained as its own document at the date it was decided. Hard identifiers (phone, payee account, vehicle, address, garage, surveyor, hospital, doctor, agent) are passed as typed **entities** *and* as **tags**. |
| **recall** with `tags` + `tags_match="any_strict"` | Exact linking: one recall per identifier ("every memory tagged `phone:9848…`"). This is how two claimants who never met turn out to share a bank account. |
| **recall** (semantic + keyword + graph arms, reranked) with `min_scores={"reranker": …}` | "Have we heard this story before?" Finds templated narratives across different people, with a relevance floor so weak matches don't become links. |
| **recall** with `temporal_window` + `query_timestamp` | "What happened around this time?" Bursts of similar claims before the intimation date. |
| **recall** with `types=["observation"]` | Pulls Hindsight's auto-consolidated observations: patterns it has merged across many claims. |
| **reflect** with mission + **directives** + disposition | Writes the investigator briefing and answers free-form questions ("What do the Lifeline claims have in common?"). Directives encode SIU rules of evidence: *a pattern is a lead, not proof*; *cite claim IDs*; *volume is not fraud*; *respect cleared outcomes*. Disposition: skepticism 4, literalism 4, empathy 2. |
| **mental model** (`refresh_after_consolidation`) | The *SIU fraud playbook*: a living summary of confirmed modus operandi and cleared look-alikes. Nobody writes it; it rebuilds as outcomes arrive. |
| **retain_mission / observations_mission** | Tells Hindsight what matters when extracting facts from claim files, and what to consolidate. |

## Does memory actually help? (replay evaluation)

`scripts/replay_eval.py` replays nine months of claims **in date order** into a fresh bank. Each claim is scored with and without memory by the same model before it is retained. Investigator outcomes enter memory on the day they were decided, so memory never sees the future. Ground truth is used only for scoring.

```bash
python scripts/replay_eval.py --sample 70
```

Outputs `data/eval/results.md`, `results.json` (shown in the app under **Does memory help?**) and `learning_curve.png`.

## Data

`scripts/generate_data.py` builds a seeded, realistic dataset: 213 motor and health claims from Hyderabad, January to September 2026. Real areas, police stations, IFSC-style accounts and IDVs; invented people and businesses. Four fraud patterns are hidden inside:

| Ring | Pattern | Why one-claim review misses it |
|---|---|---|
| R1 | Garage + surveyor collusion: staged night-time rear-end hits, inflated repairs | Each story is plausible; only the repeated surveyor, shared phones/accounts and templated wording give it away |
| R2 | Hospital admission ring: 1–2 day weekend admissions on 5-week-old policies from one agent | Each admission is medically plausible |
| R3 | Early-claim intermediary: old cars insured at high IDV, "stolen"/"burnt" within 3 weeks, one apartment block | Early claims happen; the address cluster doesn't show on one file |
| R4 | Recycled damage: same vehicle, same damage, new owner | Different policy, different garage |

Early claims in each ring were paid before anyone noticed, just like in real life. Memory has to connect them later.

## Run it

Requirements: Python 3.11+, Node 18+, a [Hindsight Cloud](https://ui.hindsight.vectorize.io) API key (or self-hosted Hindsight) and a [Groq](https://groq.com) key (any OpenAI-compatible endpoint works).

```bash
cp .env.example .env              # add HINDSIGHT_API_KEY and GROQ_API_KEY
pip install -r requirements.txt
(cd frontend && npm install && npm run build)

python scripts/seed_memory.py     # configure the bank + load Jan-Aug history
uvicorn claimlens.api:app --app-dir backend --port 8000
# open http://localhost:8000
```

Offline UI development without keys: `CLAIMLENS_FAKE_MEMORY=1 CLAIMLENS_FAKE_LLM=1 uvicorn ...`. This uses naive in-process stand-ins (clearly bannered in the UI), not Hindsight.

Tests: `pytest` (18 tests, no network). `tests/test_hindsight_contract.py` pushes every memory call through the real `hindsight-client` request models with only HTTP stubbed.

## Architecture

```
            ┌──────────────── React workbench ────────────────┐
            │ queue · claim · with/without · evidence graph   │
            │ outcome buttons · live memory activity · ask    │
            └───────────────────────┬─────────────────────────┘
                                    │ FastAPI
┌───────────────────────────────────▼───────────────────────────────────┐
│ Investigator agent (agent.py)                                         │
│   plan_probes ─► 10× recall in parallel ─► link + rank ─► LLM (JSON)  │
│                                   │                  ▲                 │
│   same prompt, no history ────────┼──────────────────┘ (baseline)     │
│   outcome ─► retain ──────────────┤                                    │
└───────────────────────────────────┼───────────────────────────────────┘
                                    ▼
             Hindsight bank "claimlens-siu"
             claims · outcomes · entities · tags · observations
             mission · directives · disposition · SIU playbook mental model
```

Robustness: the model is asked for JSON (no function calling). Responses go through lenient parsing, retries with backoff and `Retry-After`, JSON mode switched off on retries, a fallback model, then a deterministic link-strength score. The band is always derived from the score, and uncited claim IDs are removed. One failed recall probe never sinks an investigation.

## Repo map

```
backend/claimlens/
  memory.py        Hindsight bank setup, retain/recall/reflect, probes, op log
  agent.py         investigator: evidence ranking, prompts, validation, graph
  claims.py        claims system of record, rendering, entity extraction
  llm.py           defensive OpenAI-compatible client
  api.py           FastAPI routes + static UI
scripts/           generate_data · seed_memory · replay_eval
frontend/src/      React + TypeScript UI (no UI libraries)
tests/             pytest suite
```

ClaimLens recommends; people decide. It never repudiates a claim on its own.
