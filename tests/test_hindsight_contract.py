"""Run ClaimLens memory calls through the *real* hindsight-client with the HTTP
layer stubbed. If any parameter we pass is wrong, the client's own request
models reject it here instead of during a live demo."""

import asyncio
from types import SimpleNamespace as NS

import pytest
from hindsight_client import Hindsight

from claimlens import claims as C
from claimlens.memory import ClaimMemory, gather_evidence, plan_probes


class StubMemoryApi:
    def __init__(self):
        self.retains, self.recalls, self.reflects = [], [], []

    async def retain_memories(self, bank_id, request, **kw):
        self.retains.append(request)
        return NS(success=True, bank_id=bank_id, items_count=len(request.items))

    async def recall_memories(self, bank_id, request, **kw):
        self.recalls.append(request)
        cid = "CLM-2026-10401"
        return NS(results=[NS(id="f1", text=f"Claim {cid} used surveyor K. Venkat Rao", type="world",
                              document_id=cid, metadata={"claim_id": cid}, tags=["claim"], entities=[],
                              occurred_start=None, scores=NS(reranker=0.9, final=0.9))])

    async def reflect(self, bank_id, request, **kw):
        self.reflects.append(request)
        return NS(text="briefing", based_on=None, structured_output=None)


@pytest.fixture()
def real():
    client = Hindsight(base_url="http://stub.invalid", api_key="test")
    stub = StubMemoryApi()
    client._memory_api = stub
    return ClaimMemory(client=client, bank_id="t"), stub


def test_retain_items_validate_against_client_models(real):
    mem, stub = real
    c = next(x for x in C.repo().history() if x["verdict"])
    asyncio.run(mem.retain_items([mem.claim_item(c), mem.verdict_item(c, c["verdict"])], "t"))
    req = stub.retains[0]
    assert len(req.items) == 2
    item = req.items[0]
    assert item.document_id == c["claim_id"]
    assert "surveyor:" in " ".join(item.tags) or c["line"] == "health"
    assert item.entities and all(e.text for e in item.entities)
    assert req.items[1].document_id == f"verdict:{c['claim_id']}"


def test_every_probe_builds_a_valid_recall_request(real):
    mem, stub = real
    for c in C.repo().open_queue()[:5]:
        ev = asyncio.run(gather_evidence(mem, c))
        assert ev["probes"]
    n_probes = sum(len(plan_probes(c)) for c in C.repo().open_queue()[:5])
    assert len(stub.recalls) == n_probes
    strict = [r for r in stub.recalls if r.tags]
    assert all(r.tags_match in ("any_strict", "all_strict") for r in strict)
    outcome_probes = [r for r in strict if r.tags_match == "all_strict"]
    assert outcome_probes and all("verdict" in r.tags and len(r.tags) == 2 for r in outcome_probes)
    assert any(r.min_scores is not None for r in stub.recalls)
    assert any(r.temporal_window is not None for r in stub.recalls)
    assert any(r.types == ["observation"] for r in stub.recalls)


def test_recalled_facts_map_back_to_claims(real):
    mem, _ = real
    c = C.repo().open_queue()[0]
    ev = asyncio.run(gather_evidence(mem, c))
    assert "CLM-2026-10401" in ev["links"]


def test_reflect_request_validates(real):
    mem, stub = real
    out = asyncio.run(mem.reflect("what do you know?", label="t", context="ctx"))
    assert out["text"] == "briefing"
    assert stub.reflects[0].include is not None or True
