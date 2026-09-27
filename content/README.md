# Content kit

Everything here follows the content guide. Hard rule: **the word "hackathon" must not appear in any article, post, title, hashtag or video title.** Check with Ctrl+F before publishing.

Each team member publishes **their own** article (800–1,500 words) and LinkedIn post. The team publishes **one** YouTube video (2–5 min).

| File | What |
|---|---|
| `titles.md` | 20 title options (Prompt 1 rules) |
| `article.md` | Full draft article (Prompt 2 rules) with `{{PLACEHOLDERS}}` for real eval numbers |
| `linkedin.md` | Post drafts, one per angle (Prompt 3 rules, <800 chars) |
| `video.md` | 3-minute script, 5 YouTube titles, thumbnail prompt (Prompts 5–6) |

## Different angles for each teammate (same project, different article)

1. **Memory design:** "My fraud agent was blind to fraud rings until I gave it memory" (`article.md`)
2. **Evaluation:** "How I proved agent memory works: replaying nine months of claims". Focus on `scripts/replay_eval.py`, the ablation design, no-future-leak, and the learning curve.
3. **Data:** "Building a fake insurance fraud ring realistic enough to fool an LLM". Focus on `scripts/generate_data.py`, the decoys, and why early ring claims being paid matters.
4. **Frontend / UX:** "Making agent memory visible: an evidence graph and a live memory log". Focus on the UI, the evidence graph, and the memory activity panel.

Run Prompt 2 from the content guide in Claude Code at the repo root with your chosen title to get a draft for angles 2–4, then edit it into your own voice.

## Publishing checklist
- [ ] Numbers come from `data/eval/results.md` (real run, not offline mode)
- [ ] Screenshots: compare cards, evidence graph, memory activity, playbook, learning curve
- [ ] Links present: https://github.com/vectorize-io/hindsight · https://hindsight.vectorize.io/ · https://vectorize.io/what-is-agent-memory
- [ ] Published publicly (Medium / Dev.to / Hashnode / LinkedIn Article)
- [ ] Shared as a Link post on r/LLMDevs, r/SideProject, r/AI_Agents or r/aimemory
- [ ] LinkedIn post: repo link in the post body, article URL + Hindsight repo as comments
