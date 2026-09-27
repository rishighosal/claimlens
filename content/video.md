# Team video: script, titles, thumbnail

Length ~3:00. Screen recording + face cam if possible, 1080p, font zoom 110–125%. Follow `docs/DEMO.md` for exact clicks; this is the narration.

## Script

**[0:00–0:30] Intro (face cam, then app)**
"Hi, I'm [NAME]. We built ClaimLens, a claims triage agent for insurance fraud investigators that remembers every claim it has ever seen. Fraud rings are invisible if you look at one claim at a time. They only show up across history, so we gave the agent a memory: Hindsight."
*On screen: app with the September queue.*

**[0:30–1:00] The problem: an agent without memory**
"Here's a claim. A Creta, rear-ended at night by a vehicle that drove off, ₹82,400. I'll investigate it. On the left is the same model with no history. It says fast-track: looks normal, pay it."
*On screen: #10595, click Investigate, point at the grey 'Without memory' card.*

**[1:00–2:30] The demo: retain and recall live**
"On the right, the same model and prompt, with Hindsight. Refer to SIU. Watch the memory panel: it ran a separate recall for the phone, the bank account, the surveyor and the story."
*Point at Live activity: the RECALL rows and their tags.*
"The phone matches a claim investigators repudiated in August. The bank account matches one from July. Same surveyor on all of them. Every red flag cites a claim ID, and this graph shows the ring."
*Hover shared-phone node.*
"I'll confirm fraud. That's a retain; memory just learned it. Next claim from the same ring, nine days later: it now cites the claim I just closed."
*Confirm fraud → open #10606 → Investigate → point at #10595 in evidence.*
"And it doesn't over-flag. Same garage, different surveyor: memory knows those were genuine, so it stays low."
*#10614 → Investigate.*
"Ask memory anything. It reflects over the whole bank using our SIU rules of evidence."
*Ask: 'What do the Lifeline Multispeciality claims have in common?'*

**[2:30–3:00] Takeaway**
"We replayed nine months of claims to measure it. Same model with and without memory. Without memory it caught zero fraud all year. With Hindsight, once investigators had confirmed the first cases, it caught eleven of the twelve fraud claims in August and September, and it never flagged an honest claim. What surprised me: storing investigator *outcomes*, not just claims, is what made it learn. That's ClaimLens."
*On screen: Does memory help? tab.*

## YouTube titles
1. My AI Agent Caught a Fraud Ring a Normal LLM Missed
2. Same LLM, With vs Without Memory: The Difference Is Shocking
3. I Gave an AI Investigator Memory. It Found What Humans Missed
4. How Agent Memory Turns an LLM Into a Fraud Investigator (Hindsight Demo)
5. This AI Remembers Every Insurance Claim It Has Ever Seen

## Thumbnail prompt (Google Nano Banana, attach a teammate photo)
Generate a viral YouTube thumbnail, 16:9. On the left, the attached person looking surprised, pointing right. On the right, a dark dashboard with a glowing red network graph linking insurance claim cards, one card stamped "FRAUD" in red. Large bold text top-right: "IT REMEMBERED." Small label: "Same AI. + Memory." High contrast, purple and red accents, clean, no clutter. Video script: [paste the script above]
