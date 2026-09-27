# LinkedIn post drafts (<800 characters each; one per teammate)

Post the article URL as the first comment and the Hindsight repo as a second comment:
"Try Hindsight here: https://github.com/vectorize-io/hindsight"

---

## Post A (memory design)

Your fraud model isn't bad at fraud. It's amnesiac.

I gave an LLM a staged car-accident claim. It said "fast-track". The phone number belonged to a claimant we'd already repudiated.

Fraud rings don't show up in one claim. They show up across history.

What worked:
→ Store every claim AND every investigator outcome as memory
→ One strict-tag recall per identifier: phone, bank a/c, vehicle, surveyor
→ Same model, with vs without memory: fast-track → refer to SIU
→ Strip any claim ID the model cites that memory didn't return

Using Hindsight agent memory was the best call we made. The agent learns from every closed case.

Code: [REPO LINK]

#AIAgents #AgentMemory #Hindsight #LLM

---

## Post B (evaluation)

"Our agent has memory" is a claim. Here's how we tested it.

We replayed 9 months of insurance claims in date order. Every claim was scored twice by the same model: alone, and with Hindsight memory. Outcomes entered memory only on the day they were decided.

Result: {{RECALL_WITHOUT}} → {{RECALL_WITH}} of fraud claims flagged.

The shape is the point:
→ The first claims of a new ring get missed. Nothing to remember yet.
→ After investigators close a few, memory catches the rest.
→ Without memory, the line stays flat.

If you're adding memory to an agent, run the ablation. Picking Hindsight made that easy.

Code: [REPO LINK]

#AIAgents #AIMemory #Hindsight #LLM

---

## Post C (data / decoys)

The hardest part of building a fraud agent: making it NOT flag honest people.

We hid 4 fraud rings in 215 synthetic claims. We also added traps: a busy dealer that's completely clean, and honest claims at the fraud garage.

A keyword rule flags both. Our agent doesn't, because Hindsight memory holds the outcome of every past claim:
→ "Approved, surveyor assessment accepted" lowers suspicion
→ Garage + same surveyor + shared phone raises it
→ Directive in the memory bank: volume is not fraud

Memory is how an agent learns nuance, not just recall.

Code: [REPO LINK]

#AIAgents #AgentMemory #Hindsight #AI
