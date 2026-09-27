# Submission kit

Copy-paste text for the final submission form, and a checklist. Only one submission is allowed, so tick every box first.

---

## Project name
ClaimLens

## One-liner (≤ 100 characters)
Insurance fraud triage that remembers every claim, built on Hindsight agent memory.

## Short description (~50 words)
ClaimLens is a fraud-triage agent for an insurer's Special Investigation Unit. Fraud rings are invisible one claim at a time, so ClaimLens uses Hindsight as institutional memory: every claim and every investigator outcome is retained, and each new claim is checked against all of it. Same model, same prompt: 0/12 fraud caught without memory, 11/12 with Hindsight.

## Long description (~250 words)
Organised insurance fraud (garage–surveyor collusion, hospital admission rings, recycled vehicle damage) looks genuine on any single claim. The evidence sits in the history: the same surveyor on ten earlier claims, two unrelated claimants sharing a phone, a payee account that was already repudiated. Indian insurers lose an estimated ₹8,000–10,000 crore a year to fraud, waste and abuse, and IRDAI's 2025 fraud-monitoring guidelines (in force from April 2026) require every insurer to run a Fraud Monitoring Unit.

ClaimLens gives that unit a memory. When a claim arrives, the agent asks Hindsight 15–17 targeted questions in parallel: who else has this phone, account, vehicle or surveyor; what did investigators decide about them; have we heard this story before. It grades each linked claim STRONG or WEAK, and scores the claim twice with the same model and prompt, once without memory and once with. The investigator sees both side by side, with red flags that cite past claim IDs and an evidence graph of the ring. When they record an outcome, it is retained, and the next claim from the same ring is judged with it.

We measured it. Replaying nine months of claims in date order, without future leakage: without memory the model caught 0 of 33 fraud claims. With Hindsight, detection went 0% → 43% → 100% → 86% as investigators confirmed cases, catching 11 of 12 in August–September, with zero genuine claims flagged.

## How Hindsight memory is used (~200 words)
Hindsight is ClaimLens's only knowledge of the past.
- **Retain.** Each claim is retained at intake: document ID = claim ID, timestamp = intimation date, and every identifier (phone, bank account, vehicle, address, garage, surveyor, hospital, doctor, agent) passed as a typed entity and as a tag. Each investigator outcome is retained as its own dated `verdict:` document with the same tags. That is what makes the agent learn.
- **Recall.** Each new claim triggers 15–17 recalls:
  - tag-scoped "who else has X" (`any_strict`)
  - "what did SIU decide about X" (`verdict` + entity, `all_strict`)
  - a reranked semantic "have we heard this story before" with a `min_scores` reranker floor
  - a `temporal_window` recall of recent activity
  - an observations recall for consolidated patterns
- **Reflect.** Investigator briefings and free-form questions run through `reflect`, under a bank mission, four directives (lead ≠ proof, cite claim IDs, volume ≠ fraud, respect cleared cases) and a disposition of skepticism 4, literalism 4, empathy 2.
- **Mental model.** An *SIU fraud playbook* refreshes after consolidation and summarises confirmed patterns.
- **Measured.** A leak-free replay compares the same model with and without memory: 0/12 vs 11/12 fraud caught in Aug–Sep, 0 false positives.

Details: docs/HINDSIGHT.md in the repo.

## Tech stack
Hindsight Cloud (hindsight-client 0.10) · Groq `openai/gpt-oss-120b` (backups: gpt-oss-20b, qwen3.8-27b) · Python 3.11 / FastAPI · React + TypeScript (Vite) · pytest + GitHub Actions

## Links
- GitHub: https://github.com/rishighosal/claimlens
- Demo video (YouTube): …
- Articles, one per member: …
- LinkedIn posts, one per member: …

---

## Final checklist (before pressing Submit)

**Repo**
- [ ] Public; README shows the learning curve and architecture images; CI badge is green
- [ ] Video link added to the README (the `DEMO-VIDEO` comment line near the top)
- [ ] No `.env`, no `.venv` in the repo

**Video (one per team)**
- [ ] 2–5 min, 1080p, public on YouTube, custom thumbnail
- [ ] Shows: the problem, without vs with memory, confirm fraud → next claim learns, the honest claim staying low, the learning curve
- [ ] Title and description don't contain the word "hackathon"

**Content (every member)**
- [ ] Article (800–1,500 words) public on Medium / Dev.to / Hashnode / LinkedIn Articles
- [ ] Links in the article: github.com/vectorize-io/hindsight, hindsight.vectorize.io, vectorize.io/what-is-agent-memory
- [ ] Article shared as a Reddit link post (r/LLMDevs, r/SideProject, r/AI_Agents or r/aimemory)
- [ ] LinkedIn post with the repo link in the body; first comment = article link; comment with the Hindsight repo link
- [ ] Ctrl+F "hackathon" in every article, post and hashtag: must be zero

**Team**
- [ ] Every member completed the Profile Review Form
- [ ] Every link opened in an incognito window
- [ ] Submitted once, before the deadline
