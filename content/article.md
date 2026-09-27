<!--
DRAFT for one team member. Before publishing:
  1. Numbers below are from the real replay run (data/eval/results.md). Keep them in sync if you re-run it.
  2. Add the 4 screenshots listed in docs/DEMO.md where marked [IMAGE].
  3. Make it sound like you. Each teammate should take a different angle (see content/README.md).
  4. Delete this comment block before publishing, and make sure the event name never appears (hashtags included).
-->

# My fraud agent was blind to fraud rings until I gave it memory

The claim looked fine. A Hyundai Creta, rear-ended late at night near JNTU junction by a vehicle that drove off. ₹82,400 in rear-end damage, a well-known multibrand garage, a licensed surveyor's sign-off. I gave it to a good LLM with a careful fraud-triage prompt and it said what any tired claims handler would say: *fast-track, pay it.*

It was the eleventh claim in an organised fraud ring. The claimant's phone number belonged to another claimant from April. The payee bank account was on a July claim with the same "hit from behind by an unknown vehicle" story, which our investigators repudiated. The same surveyor had approved every one of them.

None of that is in the claim. It's in the *history*. That's the whole problem with insurance fraud triage, and it's why I built ClaimLens around an agent memory instead of a better prompt.

## What ClaimLens does

ClaimLens is a triage workbench for an insurer's Special Investigation Unit (SIU). A new motor or health claim comes in, and the agent does three things:

1. **Asks memory about it.** Every hard identifier on the claim (phone, payee account, vehicle registration, address, garage, surveyor, hospital, doctor, agent code) becomes its own targeted question. So does the claimant's story, and so does "what happened around this time?"
2. **Scores it twice.** The same model with the same prompt scores the claim once on its own and once with everything memory recalled. The UI puts the two side by side. The only variable is memory.
3. **Learns from the outcome.** When an investigator closes the claim (approved, cleared, referred, or fraud confirmed), that outcome is written back to memory with its date and reasons. The next claim that touches the same people, providers or story is judged with it.

The memory layer is [Hindsight](https://github.com/vectorize-io/hindsight), an open-source agent memory system from Vectorize. How I used it mattered far more than the prompt.

[IMAGE: side-by-side "Without memory" vs "With Hindsight memory" cards on the same claim]

## The through-line: turning "memory" into questions an investigator would ask

My first version did the obvious thing: dump the claim text into a semantic recall and hope the right history came back. It sort of worked. It also linked every rear-end collision to every other rear-end collision, which is useless. Fraud rings don't share *topics*; they share *identifiers*, and sometimes the same story.

So the agent now plans explicit probes. Each identifier gets its own recall, scoped with a strict tag filter:

```python
def plan_probes(claim: dict) -> list[Probe]:
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
        min_scores={"reranker": settings.narrative_min_rerank},
    ))
    ...
```

This works because of how claims go *into* Hindsight. At intake, each claim is retained as a readable claim file, with its intimation date as the timestamp, the claim ID as the document ID, and every identifier passed twice: as a typed entity (so Hindsight's graph can connect them) and as a tag (so I can filter on it exactly):

```python
return {
    "content": C.render(claim),
    "timestamp": C.as_datetime(claim["intimation_date"]),
    "document_id": claim["claim_id"],
    "metadata": {"claim_id": claim["claim_id"], "kind": "claim"},
    "entities": [{"text": e.label, "type": e.kind} for e in ents],
    "tags": ["claim", f"line:{claim['line']}", *[e.tag for e in ents]],
}
```

Tag-scoped recalls give exact links ("these three claimants share one phone"). The narrative probe uses [Hindsight's retrieval](https://hindsight.vectorize.io/), which runs semantic, keyword, graph and temporal search in parallel and reranks. It catches what tags can't: different people telling a staged accident in almost the same words. The `min_scores` reranker floor was a late fix. Semantic search always returns *something*, and without a floor every claim had a "similar story".

[IMAGE: evidence graph: new claim in the centre, shared phone / account / surveyor nodes, past claims around it, confirmed-fraud claims outlined in red]

## Outcomes are memories too

The part I underestimated was investigator outcomes. A claim file tells you what someone *said*. An outcome tells you what turned out to be *true*. I retain outcomes as separate documents, dated when they were decided, carrying the same entity tags as the claim:

```python
"content": C.render_verdict(claim, verdict),   # "SIU CONFIRMED FRAUD ... Investigator notes: ..."
"timestamp": C.as_datetime(verdict["closed_on"]),
"document_id": f"verdict:{claim['claim_id']}",
"tags": ["verdict", f"decision:{verdict['decision']}", *[e.tag for e in ents]],
```

That gives the demo its best moment: I confirm fraud on one claim, open the next claim from the same ring, and its evidence now includes the claim I closed a minute ago. That took one retain call, with no retraining and no re-indexing.

Outcomes also keep the agent from being paranoid. An honest claim at the ring's own garage, with a different surveyor, first scored 80 with a smaller model. The fix was to label every recalled link STRONG (a shared phone, bank account or vehicle, or the same surveyor as *confirmed* fraud) or WEAK (only a shared garage or story) before the model sees it. The same claim now scores 22.

## Rules of evidence, in the memory bank itself

Hindsight banks have a mission, directives and a disposition, and `reflect` reasons with all three. I used that to encode how an SIU is supposed to think:

- *A pattern in history is a lead for investigation, never proof.*
- *Every connection to past claims must cite claim IDs.*
- *High claim volume at a garage or hospital is not suspicious by itself.*
- *If investigators previously cleared a similar claim, say so and lower suspicion.*

The disposition is skepticism 4, literalism 4, empathy 2. The investigator briefing and the "ask memory" box both go through `reflect`, so the rules apply there too. Citations are also enforced in code: any claim ID the model cites that memory didn't return is stripped.

A Hindsight [mental model](https://vectorize.io/what-is-agent-memory) called *SIU fraud playbook* rounds it out. It refreshes after consolidation and rewrites itself into a readable summary of confirmed patterns as outcomes accumulate. Nobody wrote it.

[IMAGE: the Playbook panel]

## Did memory actually help?

I didn't want to eyeball this, so I wrote a replay. It plays nine months of claims through the system in date order, into a fresh bank. Each claim is scored with and without memory *before* it is retained. Investigator outcomes enter memory on the day they were decided, so memory never sees the future.

Same model, same prompt:

| | Without memory | With Hindsight |
|---|---|---|
| Fraud claims flagged, whole year | 0 of 33 | 14 of 33 |
| Fraud claims flagged, Aug–Sep | 0 of 12 | 11 of 12 |
| Genuine claims wrongly flagged | 0 | 0 |
| ROC AUC | 0.46 | 0.79 |
| Fraud value flagged | ₹0 | ₹36.7 lakh |

Month by month, the share of fraud claims flagged with memory went 0% (March–June), 43% (July), 100% (August), 86% (September). Without memory it was 0% every month. The model was the same, `gpt-oss-120b`, and so was the prompt.

[IMAGE: data/eval/learning_curve.png]

The shape matters more than the totals. From March to June memory catches nothing either, and that's correct: the ring's early claims were paid, nothing was confirmed yet, and "same garage, same surveyor, claims approved" isn't evidence. In July investigators repudiate the first ring claims, those outcomes land in Hindsight, and the curve jumps. In August every fraud claim was flagged, and not one genuine claim was flagged in the whole replay.

The honest miss: the recycled vehicle. Both repeat claims on the same Creta scored 45, which means "standard review", not "refer". Nobody had confirmed anything about that car, so the agent sent it for review rather than to SIU. For an SIU that's the right bias, because a false accusation is expensive.

## What I'd tell someone building this

1. **Design memory writes for the reads you need.** Identifiers as both entities and tags made exact linking trivial.
2. **Ask many narrow questions, not one broad one.** Scoped recalls beat one big semantic query, and each explains its link.
3. **Store outcomes, not just inputs.** "What happened next" is what makes an agent *learn* instead of just search.
4. **Measure with an ablation.** The same model with and without memory is the only honest proof.
5. **Grade evidence before the model sees it.** STRONG/WEAK labels and citation checks kept it from becoming an accusation machine.

ClaimLens recommends; people decide. But now it has the one thing claims handlers never have enough of: a memory of every claim that came before.

*Code: [link to your repo]. Built on [Hindsight agent memory](https://github.com/vectorize-io/hindsight).*
