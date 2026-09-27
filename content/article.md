<!--
DRAFT for one team member. Before publishing:
  1. Replace every {{PLACEHOLDER}} with numbers from data/eval/results.md (never invent them).
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

The memory layer is [Hindsight](https://github.com/vectorize-io/hindsight), an open-source agent memory system from Vectorize. I'll spend most of this post on how I used it, because the design choices there mattered much more than the prompt.

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

The tag-scoped recalls give me the exact links ("these three claimants share one phone"). The narrative probe relies on [Hindsight's retrieval](https://hindsight.vectorize.io/), which runs semantic, keyword, graph and temporal search in parallel and reranks the results. That catches something tags never will: five different people describing a staged accident in almost the same sentence. The `min_scores` reranker floor was a late fix. Semantic search always returns *something*, and without a floor every claim had a "similar story".

All the probes run concurrently, and their results are folded into a ranked set of linked past claims. Personal identifiers weigh more than shared providers, and a link to a claim SIU already repudiated weighs most. Only that ranked evidence reaches the model.

[IMAGE: evidence graph: new claim in the centre, shared phone / account / surveyor nodes, past claims around it, confirmed-fraud claims outlined in red]

## Outcomes are memories too

The part I underestimated was investigator outcomes. A claim file tells you what someone *said*. An outcome tells you what turned out to be *true*. I retain outcomes as separate documents, dated when they were decided, carrying the same entity tags as the claim:

```python
"content": C.render_verdict(claim, verdict),   # "SIU CONFIRMED FRAUD ... Investigator notes: ..."
"timestamp": C.as_datetime(verdict["closed_on"]),
"document_id": f"verdict:{claim['claim_id']}",
"tags": ["verdict", f"decision:{verdict['decision']}", *[e.tag for e in ents]],
```

That gives the demo its best moment. I confirm fraud on one claim, open the next claim from the same ring nine days later, and the evidence now cites the claim I closed a minute ago. Nothing was retrained or re-indexed; I made one retain call.

Outcomes also stop the agent from being paranoid. The dataset includes an authorised Hyundai dealer with far more claims than anyone else, all genuine, and genuine claims at the fraud ring's garage that were handled by other surveyors. Because memory holds "approved, surveyor assessment accepted" for those, the agent learns the actual pattern (this garage *with this surveyor*) instead of "this garage is bad".

## Rules of evidence, in the memory bank itself

Hindsight banks have a mission, directives and a disposition, and `reflect` reasons with all three. I used that to encode how an SIU is supposed to think:

- *A pattern in history is a lead for investigation, never proof.*
- *Every connection to past claims must cite claim IDs.*
- *High claim volume at a garage or hospital is not suspicious by itself.*
- *If investigators previously cleared a similar claim, say so and lower suspicion.*

The disposition is skepticism 4, literalism 4, empathy 2: sceptical and precise about identifiers, but not dismissive of genuine claimants. The investigator briefing and the "ask memory" box both go through `reflect`, so these rules apply there too.

I also enforce citations in code. If the model cites a claim ID that wasn't in the recalled evidence, it gets stripped, and the UI shows how many were removed. The model proposes; memory has to back it up.

## A playbook nobody wrote

One more Hindsight feature turned out to be the most fun to demo: [mental models](https://vectorize.io/what-is-agent-memory). I created one called *SIU fraud playbook* with a source query asking which fraud patterns investigators have confirmed, which entities were involved, and what separates them from genuine claims. It's set to refresh after consolidation. As outcomes accumulate, it rewrites itself into a readable summary of the unit's institutional knowledge, and the agent uses it in `reflect`.

[IMAGE: the Playbook panel]

## Did memory actually help?

I didn't want to eyeball this, so I wrote a replay. It plays nine months of claims through the system in date order, into a fresh bank. Each claim is scored with and without memory *before* it is retained. Investigator outcomes enter memory on the day they were decided, so memory never sees the future.

Same model, same prompt:

| | Without memory | With Hindsight |
|---|---|---|
| Fraud claims flagged | {{RECALL_WITHOUT}} | {{RECALL_WITH}} |
| Precision | {{PRECISION_WITHOUT}} | {{PRECISION_WITH}} |
| Genuine claims flagged | {{FP_WITHOUT}} | {{FP_WITH}} |

[IMAGE: data/eval/learning_curve.png]

The shape matters more than the totals. The first claims of every ring are missed with or without memory, because there's nothing to remember yet. After that, the memory arm starts catching them, and it gets better as investigators close cases. Without memory, the curve stays flat.

## What I'd tell someone building this

1. **Design memory writes for the reads you need.** Passing identifiers as both entities and tags cost nothing at write time and made exact linking trivial at read time.
2. **Make the agent ask many narrow questions, not one broad one.** Ten scoped recalls beat one big semantic query, and each one gives you an explainable reason for the link.
3. **Store outcomes, not just inputs.** "What happened next" is the most valuable memory a decision-support agent can have, and it's what makes the agent *learn* instead of just search.
4. **Measure with an ablation, not a demo.** Running the same model with and without memory is the only honest way to show memory did the work.
5. **Put your rules of evidence where the reasoning happens.** Directives in the bank, plus citation checks in code, kept a fraud agent from turning into an accusation machine.

ClaimLens recommends; people decide. But now it has the one thing claims handlers never have enough of: a memory of every claim that came before.

*Code: [link to your repo]. Built on [Hindsight agent memory](https://github.com/vectorize-io/hindsight).*
