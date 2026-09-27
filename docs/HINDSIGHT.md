# How ClaimLens uses Hindsight memory

ClaimLens has no database of "known fraudsters" and no hand-written rules about garages. Everything it knows about the past lives in one Hindsight memory bank, `claimlens-siu`. This document follows a claim through that memory: what is written, what is asked, and how the answers change the decision.

All code referenced here is in [`backend/claimlens/memory.py`](../backend/claimlens/memory.py) and [`backend/claimlens/agent.py`](../backend/claimlens/agent.py).

## 1. The bank is configured as an investigator, not a chatbot

`ClaimMemory.setup_bank()` configures the bank once:

| Setting | Value | Why |
|---|---|---|
| `retain_mission` | Extract every party, identifier, date, amount, damage/diagnosis, story and investigator decision, keeping the claim ID attached | Claim files are dense; this tells Hindsight's fact extraction what an SIU cares about |
| `reflect_mission` | "You are ClaimLens, the institutional memory of an insurance Special Investigation Unit…" | Frames every `reflect` answer as an investigator briefing |
| `observations_mission` | Consolidate recurring entities, shared identifiers across claimants, repeated narratives, and what investigators concluded | Steers auto-consolidation towards ring-shaped patterns |
| Disposition | skepticism 4, literalism 4, empathy 2 | Sceptical and exact about identifiers, not dismissive of genuine claimants |
| Directives | *Evidence, not verdicts* · *Cite claim IDs* · *Volume is not fraud* · *Respect cleared outcomes* | Rules of evidence enforced wherever `reflect` reasons |
| Mental model | *SIU fraud playbook*, `refresh_after_consolidation: true` | A living, human-readable summary of confirmed patterns and cleared look-alikes |

## 2. What goes in: claims at intake, outcomes at closure

**A claim** is retained when it is investigated, as a plain-text claim file:

```python
{
  "content": C.render(claim),                         # the file an investigator would read
  "timestamp": C.as_datetime(claim["intimation_date"]),
  "document_id": claim["claim_id"],
  "metadata": {"claim_id": ..., "kind": "claim", "line": "motor"},
  "entities": [{"text": "surveyor K. Venkat Rao", "type": "surveyor"}, ...],
  "tags": ["claim", "line:motor", "garage:G07", "surveyor:SV12", "phone:8819721356", ...],
  "update_mode": "replace",
}
```

Every hard identifier goes in **twice**: as a typed entity, so Hindsight's graph links claims that share it, and as a tag, so ClaimLens can ask for exactly those memories later. Writing it twice costs nothing, and it made the reads simple and exact.

**An outcome** is retained when an investigator closes the claim, as its own document (`verdict:<claim_id>`). Its timestamp is the decision date, and it carries the same entity tags plus `verdict` and `decision:<...>`. The text is written for memory: *"the claim SIU CONFIRMED FRAUD and repudiated … Investigator notes: phone number matches earlier claimant."*

Outcomes are the most important memory in the system. A claim file records what someone *said*; an outcome records what turned out to be *true*. In the replay, the agent's detection jumps in exactly the month the first outcomes arrive.

## 3. What comes out: 15–17 targeted recalls per claim

`plan_probes()` turns one claim into the questions an experienced investigator would ask. `gather_evidence()` runs them concurrently (6 at a time).

| Probe | Hindsight call | Example on claim #10595 |
|---|---|---|
| Who else has this identifier? (×7 motor / ×6 health) | `recall(tags=["phone:8819721356"], tags_match="any_strict")` | Phone is on #10466, #10540 (paid) and #10572 (repudiated) |
| What did SIU decide about it? (×7 / ×6) | `recall(tags=["verdict", "surveyor:SV12"], tags_match="all_strict")` | Surveyor SV12 is on 5 repudiated claims |
| Have we heard this story before? | semantic + BM25 + graph, reranked, `min_scores={"reranker": 0.55}` | Several near-identical "unknown vehicle hit from behind and fled" stories from other claimants |
| What happened around this time? | `temporal_window` = 90 days before intimation, `query_timestamp` | Recent Sri Balaji claims |
| Does this match a known pattern? | `types=["observation"]` | Hindsight's consolidated observations about the garage–surveyor pair |

The results are mapped back to claim IDs (through `document_id` / `metadata.claim_id`) and folded into **links**: *past claim X is connected to this one via: shared phone, same surveyor, similar story; outcome: fraud confirmed*.

Two details mattered in practice:

- **The reranker floor.** Semantic search always returns *something*. Without `min_scores`, every rear-end claim had a "similar story" with every other one.
- **The recall anchor.** The replay passes the claim's own date as `query_timestamp`, so memory never sees the future. The live app passes *now*, so an outcome an investigator recorded a minute ago ranks as the freshest knowledge.

## 4. Grading the evidence before the model sees it

Every link is labelled before it reaches the language model:

- **STRONG:** a shared phone, bank account or vehicle with a different claim, or the same surveyor/doctor as a claim SIU *confirmed* as fraud.
- **WEAK:** shares only a garage, hospital, agent or a similar story.

The prompt tells the model to score from STRONG evidence. Without this step, a smaller model flagged an honest claim at the ring's garage at 80. With it, the same claim scores 22. The model is never allowed to decide what counts as evidence on its own.

## 5. Same model, with and without memory

For every claim the agent makes two calls with the **same model and the same system prompt**. One sees the claim alone; the other sees the claim plus the graded HISTORY recalled from Hindsight. The UI shows both side by side, and the replay evaluation measures the difference across 215 claims (see the README).

Any claim ID the model cites that memory did not return is stripped, and the UI shows how many were removed.

## 6. Reflect and the playbook

- **Investigator briefing** (button on each claim): `reflect(query=..., context=<claim file>, budget="mid", include_facts=True)`. The answer follows the bank's mission and directives and reports how many memories it used.
- **Ask memory** (side panel): free-form `reflect` over the whole bank, e.g. *"What do the Lifeline Multispeciality claims have in common?"* or *"Has vehicle TS08FK4521 been claimed before?"*
- **SIU fraud playbook**: a mental model with the source query *"What fraud patterns have SIU investigators confirmed … and what separates them from genuine claims?"* Hindsight refreshes it after consolidation, so it rewrites itself as outcomes accumulate.

## 7. The learning loop in one sentence

An investigator clicks **Confirm fraud** → one `retain` writes the outcome with the claim's entity tags → the next claim that shares a phone, account, vehicle or surveyor gets that outcome back from its per-entity outcome probe → the link is graded STRONG → the claim is referred. No retraining, no rules edited, no re-indexing.

## 8. What production would add

- **One bank per insurer and line of business**, with the IIB caution repository and each insurer's closed claims replayed in as history, the same way `seed_memory.py` does it.
- **Webhooks** on retain/consolidation to push new ring patterns to the Fraud Monitoring Unit.
- **Tag-group filters** for multi-branch deployments, so a branch sees only its own history plus shared confirmed fraud.
