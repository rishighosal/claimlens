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


class RateLimitedThenOK:
    """429 twice with a Groq-style message, then success."""

    def __init__(self):
        self.n = 0
        self.chat = NS(completions=self)

    async def create(self, **kw):
        self.n += 1
        if self.n <= 2:
            e = Exception("Error code: 429 - Rate limit reached ... Please try again in 1.5s")
            e.status_code = 429
            raise e
        return NS(choices=[NS(message=NS(content='{"risk_score": 33}'))], usage=None)


class MissingModel:
    """Primary model missing (404); the backup answers."""

    def __init__(self):
        self.calls = []
        self.chat = NS(completions=self)

    async def create(self, model, **kw):
        self.calls.append(model)
        if model == "gone":
            e = Exception("Error code: 404 - model_not_found")
            e.status_code = 404
            raise e
        return NS(choices=[NS(message=NS(content='{"risk_score": 44}'))], usage=None)


def test_rate_limits_are_waited_out_on_the_same_model(monkeypatch):
    waits = []

    async def fake_sleep(s):
        waits.append(s)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    data, src = asyncio.run(LLM(client=RateLimitedThenOK(), model="m1", fallback_model="m2").json("s", "u"))
    assert src == "m1" and data["risk_score"] == 33
    assert waits == [2.0, 2.0]  # parsed "try again in 1.5s" + 0.5s margin


def test_missing_model_is_skipped_immediately(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", lambda *_: _noop())
    client = MissingModel()
    llm = LLM(client=client, model="gone", fallback_model="backup")
    data, src = asyncio.run(llm.json("s", "u"))
    assert src == "backup" and client.calls == ["gone", "backup"]


def test_strict_mode_never_uses_fallback(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", lambda *_: _noop())
    llm = LLM(client=FlakyClient(99), model="m1", fallback_model="m2")
    with pytest.raises(RuntimeError):
        asyncio.run(llm.json("s", "u", fallback=lambda: {"risk_score": 5}, strict=True))


def test_fallback_score_keeps_honest_claim_at_fraud_garage_low():
    from claimlens.agent import heuristic_assessment
    from claimlens.memory import Link

    fraud_note = ["Outcome of claim X: the claim SIU CONFIRMED FRAUD and repudiated"]
    # honest claim: same garage + similar story as fraud claims, same (clean) surveyor as approved ones
    honest = [(Link("A", {"garage", "narrative"}, [], fraud_note), 3.0),
              (Link("B", {"garage", "narrative"}, [], fraud_note), 3.0),
              (Link("C", {"surveyor", "narrative"}, [], ["approved and paid"]), 2.0)]
    ring = [(Link("D", {"garage", "surveyor", "narrative"}, [], fraud_note), 6.0),
            (Link("E", {"phone", "surveyor"}, [], fraud_note), 7.0),
            (Link("F", {"account", "surveyor"}, [], ["approved and paid"]), 5.0)]
    recycled = [(Link("G", {"vehicle"}, [], ["approved and paid"]), 3.0),
                (Link("H", {"vehicle"}, [], ["approved and paid"]), 3.0)]
    assert heuristic_assessment({}, honest)["risk_score"] <= 30
    assert heuristic_assessment({}, ring)["risk_score"] > 60
    assert heuristic_assessment({}, recycled)["risk_score"] > 60
