# Presenter kit

Everything the team needs to present ClaimLens: the one-liner, the 3-minute finale talk, the video structure, likely judge questions with honest answers, and a presentation-day checklist.

Deck: [`docs/ClaimLens-pitch.pptx`](ClaimLens-pitch.pptx), 10 slides with speaker notes on every slide.

---

## The one-liner (memorise this)

> **Fraud rings are invisible one claim at a time. ClaimLens gives the claims-triage agent a memory of every claim and every investigator decision, using Hindsight. Same model, same prompt: 0 of 12 fraud claims caught without memory, 11 of 12 with it, and no honest claims flagged.**

## The 3 things judges must remember

1. **The problem is real and specific:** organised fraud hides in the pattern *between* claims. It costs Indian insurers ₹8,000–10,000 crore a year, and IRDAI's rules have required every insurer to run a Fraud Monitoring Unit since 1 April 2026.
2. **Memory is the product:** it recalls what an investigator would ask, grades evidence STRONG or WEAK, and learns from every outcome.
3. **It's measured:** a leak-free replay shows the learning curve (0% → 43% → 100% → 86%) with zero false positives.

---

## Finale talk track (3 minutes + demo)

| Time | Slide / screen | Say (natural, not memorised word for word) |
|---|---|---|
| 0:00 | Slide 1 | "We built ClaimLens, a fraud-triage agent that remembers every claim it has ever seen, using Hindsight. One number: same model, same prompt, zero of twelve fraud claims caught without memory, eleven of twelve with it." |
| 0:15 | Slide 2 | "Three real claims from our dataset. Priya, Sneha, Suresh. Different people, different cars. Each one is a routine hit-and-run, and a model reading one claim scores Suresh 15 out of 100. But Suresh's phone is Sneha's phone, his bank account is Priya's, the same surveyor signed off all three, and investigators repudiated Priya's and Sneha's claims on 7 and 8 September. None of that is in Suresh's file. It's in the history." |
| 0:50 | Slide 3 | "This costs Indian insurers eight to ten thousand crore a year, and since April IRDAI requires every insurer to run a Fraud Monitoring Unit." |
| 1:05 | Slide 4 | "Rules over-flag: 'flag this garage' also hits the 7 honest customers there. Chatbots forget. Memory learns combinations." |
| 1:20 | Slide 5 | "Every claim and every investigator outcome is retained into Hindsight. For a new claim the agent asks memory 17 questions, grades what comes back STRONG or WEAK, and scores the claim twice: without memory and with." |
| 1:40 | **Live app** | Follow the guided demo strip: #10595 (15 → 87), Confirm fraud, #10606 cites it, #10614 stays at 22, #10597 flags the recycled car. *(If time is short: #10595 → Confirm → #10606 only.)* |
| 2:40 | Slide 7 | "And we measured it. Nine months replayed in date order; memory never sees the future. Nothing caught until investigators confirm the first cases in July, then 43, 100, 86 percent. Zero honest claims flagged." |
| 2:55 | Slide 10 | "Fraud rings hide in history. ClaimLens remembers it. Thank you." |

If there's no time for the live demo, slide 6 shows the same four claims with real scores.

---

## Video (2–5 min, one per team)

Record the app, not the slides, except for a 5-second title card if you like.

1. **0:00–0:35: "The problem" screen.** It opens first on a fresh browser. Read the headline, then click **Reveal what memory sees** and let the five lines appear. This is the hook: the viewer *sees* the ring before you explain anything.
2. **0:35–0:50:** scroll through "Why it matters" and "Why rules and chatbots miss it".
3. **0:50–2:30:** click **Start the guided demo** and follow the strip: #10595, Confirm fraud, #10606, #10614, #10597. Keep the right-hand memory panel in frame while it works.
4. **2:30–3:00:** the **Does memory help?** tab, then the closing line.

Cut the waiting time while investigations run (10–40 s) in editing. Narration lines are in [`content/video.md`](../content/video.md).

To see the story screen again after you've clicked away: use the **The problem** tab in the header.

---

## Judge Q&A: likely questions and honest answers

**"Isn't the data synthetic?"**
Yes, and deliberately so: real claim files contain personal data we can't publish. It's seeded and realistic (Hyderabad areas, police stations, IFSC-style accounts, real IDVs), with decoys built in to punish naive rules. The replay script is the pilot plan: run it on an insurer's own closed claims and measure the same with/without difference on their data.

**"Why is overall recall only 42%?"**
Because early ring claims were genuinely undetectable. They were paid before anyone knew, and "same garage, same surveyor, previous claims approved" isn't evidence. We don't want an agent that accuses people on that. Once investigators confirm the first cases, detection goes to 11 of 12 with zero false positives. That curve *is* the learning.

**"What stops it from wrongly accusing honest customers?"**
Four things:
- Evidence is graded STRONG or WEAK *in code* before the model sees it.
- The bank's directives say a pattern is a lead, not proof.
- Any claim ID the model cites that memory didn't return is stripped.
- The agent only recommends; an investigator decides.

The honest claim at the fraud garage scores 22, and zero genuine claims were flagged in the replay.

**"Why Hindsight and not a vector database or a graph DB?"**
We need more than similarity search:
- exact tag filters (who else has *this* phone)
- an entity graph across claims
- time-aware recall so the replay never sees the future
- consolidated observations
- `reflect` that follows rules of evidence
- a mental model that rewrites itself

Hindsight gives us all of that behind retain / recall / reflect. Building it ourselves would be the whole project.

**"How do you know the model isn't making up links?"**
Links come from memory, not the model: each one maps back to a claim ID through Hindsight's `document_id`/metadata, and the STRONG/WEAK grade is computed deterministically. The model only weighs them, and any citation it invents is removed. The UI shows every recall in the live memory panel.

**"Does it scale? Isn't 10–40 seconds slow?"**
One investigation means about 17 memory recalls (run 6 at a time) plus 2 model calls, which we ran on free tiers. For triage that's fine: SIU referrals take days today. In production the stateless arm isn't needed; it's there to prove memory's value.

**"What about privacy? This is personal data."**
Account numbers are already masked in the claim files. In production it's one Hindsight bank per insurer; Hindsight is open source and can be self-hosted inside the insurer's environment. Only identifiers needed for linking are stored, and the agent never makes a final decision.

**"How does it handle a brand-new fraud pattern?"**
Nothing to retrain. The first confirmed outcome is retained, Hindsight consolidates observations, the playbook mental model refreshes, and the next claim sharing those identifiers gets STRONG evidence. That's exactly what happens between June and August in the replay.

**"Why did the recycled car only get 45 in the replay?"**
Nothing was ever confirmed about that car, and the agent is conservative by design: one repeated identifier with no fraud finding means "standard review", not an SIU referral. In the live app, with the full history, it refers the third claim (75). We'd rather under-refer than accuse.

**"How would an insurer adopt it?"**
- **Four-week pilot:** replay their closed claims and measure the lift.
- **Shadow mode:** score new claims alongside today's process.
- **Production:** one bank per insurer, with the IIB caution repository imported.

It maps to IRDAI's framework: red-flag indicators, an incident database, a Fraud Monitoring Unit.

**"What would you build next?"**
- Health-claim document checks (bills, discharge summaries) retained as memories.
- Webhooks that alert the FMU when a new ring pattern consolidates.
- Per-branch tag groups, so a branch sees its own history plus shared confirmed fraud.

---

## Presentation-day checklist

- [ ] **Memory reset:** `python scripts/seed_memory.py --reset` (≈6 min), then `del data\state.json`
- [ ] **Browser reset:** open DevTools → Application → Local Storage → clear (or use an incognito window) so the app opens on "The problem" and the guided demo starts at 0/6
- [ ] **Playbook built:** Investigate tab → Playbook → Refresh (wait ~1 min)
- [ ] **Fresh Groq key** in `.env`, plus a second key ready (a teammate's)
- [ ] **Don't run the replay** during the presentation
- [ ] **Browser:** zoom 110%, other tabs closed, notifications off
- [ ] **Backup:** the recorded video on the laptop *and* on a phone, in case the venue Wi-Fi fails
- [ ] **Deck:** open `docs/ClaimLens-pitch.pptx` in presenter view (speaker notes visible)
- [ ] **Rehearsed:** the talk track run twice with a timer
