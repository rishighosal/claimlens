"""In-process stand-in for the Hindsight client, for offline development and tests.

It implements only the subset of the async client API that ClaimLens calls,
with deliberately naive retrieval (tag filters + word overlap). It exists so
the UI and pipeline can be exercised without network access. It is NOT a
substitute for Hindsight: no LLM fact extraction, no entity graph, no
temporal reasoning, no observation consolidation. Enable with
CLAIMLENS_FAKE_MEMORY=1; the UI shows a banner while it is active.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from types import SimpleNamespace as NS
from typing import Any

_WORD = re.compile(r"[a-z0-9]+")
_STOP = set("the a an and or of to in on at for with by from was were is are this that my i it as be had has have".split())


def _toks(s: str) -> set[str]:
    return {w for w in _WORD.findall(s.lower()) if w not in _STOP and len(w) > 2}


@dataclass
class _Fact:
    id: str
    text: str
    document_id: str
    tags: list[str]
    metadata: dict
    occurred_start: str | None
    type: str = "world"
    toks: set[str] = field(default_factory=set)


class FakeHindsight:
    is_fake = True

    def __init__(self):
        self.banks: dict[str, dict[str, Any]] = {}

    def _bank(self, bank_id: str) -> dict:
        return self.banks.setdefault(bank_id, {"facts": {}, "directives": [], "models": {}, "config": {}})

    async def acreate_bank(self, bank_id, **kw):
        self._bank(bank_id)["config"].update({k: v for k, v in kw.items() if v is not None})
        return NS(bank_id=bank_id)

    async def aupdate_bank_config(self, bank_id, **kw):
        self._bank(bank_id)["config"].update(kw)
        return {}

    async def adelete_bank(self, bank_id):
        self.banks.pop(bank_id, None)

    async def alist_directives(self, bank_id, **kw):
        return NS(items=[NS(name=d["name"]) for d in self._bank(bank_id)["directives"]])

    async def acreate_directive(self, bank_id, name, content, priority=0, is_active=True, tags=None):
        self._bank(bank_id)["directives"].append({"name": name, "content": content})
        return NS(id=name)

    async def aretain_batch(self, bank_id, items, **kw):
        b = self._bank(bank_id)
        for it in items:
            doc = it.get("document_id")
            # replace semantics per document
            for k in [k for k, f in b["facts"].items() if f.document_id == doc]:
                del b["facts"][k]
            ts = it.get("timestamp")
            for i, line in enumerate(l for l in it["content"].split("\n") if l.strip()):
                fid = f"{doc}#{i}"
                b["facts"][fid] = _Fact(fid, line.strip(), doc, list(it.get("tags") or []),
                                        dict(it.get("metadata") or {}),
                                        ts.isoformat() if hasattr(ts, "isoformat") else ts, toks=_toks(line))
        return NS(success=True, items_count=len(items))

    async def arecall(self, bank_id, query, types=None, max_tokens=4096, tags=None, tags_match="any", min_scores=None, **kw):
        b = self._bank(bank_id)
        if types and "world" not in types and "experience" not in types:
            return NS(results=[])
        q = _toks(query)
        scored = []
        for f in b["facts"].values():
            if tags:
                ft = set(f.tags)
                if tags_match in ("all", "all_strict"):
                    hit = set(tags) <= ft
                elif tags_match == "exact":
                    hit = set(tags) == ft
                else:
                    hit = bool(set(tags) & ft)
                if tags_match in ("any_strict", "all_strict", "exact") and not hit:
                    continue
            overlap = len(q & f.toks)
            if tags and set(tags) & set(f.tags):
                overlap += 3
            if min_scores and "reranker" in min_scores:
                # crude stand-in for a relevance floor: require substantial word overlap
                if len(q & f.toks) < max(4, int(len(q) * 0.45)):
                    continue
            if overlap:
                scored.append((overlap, f))
        scored.sort(key=lambda x: -x[0])
        out, budget = [], max_tokens * 4
        for _, f in scored:
            budget -= len(f.text)
            if budget < 0:
                break
            out.append(NS(id=f.id, text=f.text, type=f.type, document_id=f.document_id, tags=f.tags,
                          metadata=f.metadata, entities=[], occurred_start=f.occurred_start))
        return NS(results=out)

    async def areflect(self, bank_id, query, context=None, **kw):
        res = await self.arecall(bank_id, (context or "") + " " + query, max_tokens=900)
        facts = res.results[:8]
        text = "Offline stand-in (no Hindsight): most related memories:\n" + "\n".join(f"- {f.text}" for f in facts)
        return NS(text=text, based_on=NS(memories=facts, directives=[NS(name=d["name"]) for d in self._bank(bank_id)["directives"]]),
                  structured_output=None)

    async def acreate_mental_model(self, bank_id, name, source_query, id=None, **kw):
        self._bank(bank_id)["models"][id or name] = {"name": name, "query": source_query}
        return NS(id=id)

    async def aget_mental_model(self, bank_id, mental_model_id, detail=None):
        b = self._bank(bank_id)
        if mental_model_id not in b["models"]:
            raise KeyError(mental_model_id)
        confirmed = [f.text for f in b["facts"].values() if "CONFIRMED FRAUD" in f.text or "Investigator notes" in f.text and "Repudiated" in f.text]
        content = "Offline stand-in playbook (Hindsight builds the real one):\n" + "\n".join(f"- {t}" for t in confirmed[:12])
        return NS(name=b["models"][mental_model_id]["name"], content=content, last_refreshed_at=None, is_stale=False)

    async def arefresh_mental_model(self, bank_id, mental_model_id):
        return NS(operation_id="fake")

    async def alist_memories(self, bank_id, type=None, limit=100, **kw):
        n = len(self._bank(bank_id)["facts"]) if type in (None, "world") else 0
        return NS(items=[], total=n)
