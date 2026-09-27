"""Deterministic offline stand-in for the chat model (tests / UI work without keys).

It reads the same prompt the real model gets and scores it with crude rules,
so the pipeline, validation and UI can be exercised end to end. Numbers it
produces are meaningless as model quality and must never be reported.
"""

from __future__ import annotations

import json
import re
from datetime import date
from types import SimpleNamespace as NS


class _Completions:
    async def create(self, model, messages, **kw):
        user = messages[-1]["content"]
        content = json.dumps(score(user))
        return NS(choices=[NS(message=NS(content=content))],
                  usage=NS(prompt_tokens=len(user) // 4, completion_tokens=len(content) // 4))


class FakeLLMClient:
    def __init__(self):
        self.chat = NS(completions=_Completions())


def score(prompt: str) -> dict:
    s, flags = 12, []
    m1 = re.search(r"Policy \S+ started (\d{4}-\d{2}-\d{2}); claim intimated (\d{4}-\d{2}-\d{2})", prompt)
    if m1:
        days = (date.fromisoformat(m1.group(2)) - date.fromisoformat(m1.group(1))).days
        if days < 30:
            s += 22
            flags.append({"title": "Claim soon after policy start", "detail": f"{days} days after inception",
                          "severity": "medium", "evidence_claim_ids": []})
    hist = prompt.split("HISTORY", 1)[1] if "HISTORY" in prompt else ""
    for block in re.split(r"\n\[", hist)[1:]:
        cid = block.split("]", 1)[0]
        strong = any(k in block for k in ("shared phone", "shared payee", "same vehicle", "same address"))
        fraud = "CONFIRMED FRAUD" in block
        similar = "similar story" in block
        if fraud or strong or similar:
            s += 18 if fraud else 12 if strong else 6
            flags.append({"title": "Linked past claim", "detail": block.split("\n", 1)[0][:160],
                          "severity": "high" if fraud else "medium", "evidence_claim_ids": [cid]})
    s = min(s, 96)
    return {"risk_score": s, "band": "", "headline": "Offline stand-in assessment",
            "reasoning": "Rule-based stand-in used because CLAIMLENS_FAKE_LLM is set.",
            "red_flags": flags[:5], "mitigating_factors": [], "next_steps": ["Verify documents."],
            "questions_for_claimant": []}
