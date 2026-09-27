import asyncio
from types import SimpleNamespace as NS

import pytest

from claimlens.agent import band_for, make_validator
from claimlens.llm import LLM, extract_json


@pytest.mark.parametrize("raw", [
    '{"risk_score": 40}',
    '<think>let me reason {not json}</think>\n{"risk_score": 40}',
    '```json\n{"risk_score": 40}\n```',
    'Sure! Here is the result: {"risk_score": 40, "note": "a } inside a string"} hope it helps',
])
def test_extract_json_tolerates_model_noise(raw):
    assert extract_json(raw)["risk_score"] == 40


def test_validator_removes_uncited_ids_and_derives_band():
    v = make_validator({"CLM-2026-10401"})
    out = v({"risk_score": 250, "band": "fast_track",
             "red_flags": [{"title": "x", "detail": "y", "severity": "weird",
                            "evidence_claim_ids": ["CLM-2026-10401", "CLM-2026-99999"]}]})
    assert out["risk_score"] == 100
    assert out["band"] == "refer_to_siu"  # never trust the model's band
    assert out["red_flags"][0]["evidence_claim_ids"] == ["CLM-2026-10401"]
    assert out["red_flags"][0]["severity"] == "medium"
    assert out["uncited_ids_removed"] == 1


def test_bands():
    assert band_for(0) == "fast_track" and band_for(30) == "fast_track"
    assert band_for(31) == "standard_review" and band_for(61) == "refer_to_siu"


class FlakyClient:
    """Fails twice with garbage, then returns JSON."""

    def __init__(self, failures):
        self.n, self.failures = 0, failures
        self.chat = NS(completions=self)

    async def create(self, **kw):
        self.n += 1
        if self.n <= self.failures:
            return NS(choices=[NS(message=NS(content="I cannot comply in JSON, sorry"))], usage=None)
        return NS(choices=[NS(message=NS(content='{"risk_score": 12}'))], usage=None)


def test_llm_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", lambda *_: _noop())
    llm = LLM(client=FlakyClient(2), model="m1", fallback_model="m2")
    data, src = asyncio.run(llm.json("s", "u"))
    assert data["risk_score"] == 12 and src == "m1"


def test_llm_falls_back_deterministically(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", lambda *_: _noop())
    llm = LLM(client=FlakyClient(99), model="m1", fallback_model="m2")
    data, src = asyncio.run(llm.json("s", "u", fallback=lambda: {"risk_score": 5}))
    assert src == "fallback" and data["risk_score"] == 5
    assert llm.usage["failures"] == 1


async def _noop():
    return None
