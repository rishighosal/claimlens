"""Thin, defensive wrapper around any OpenAI-compatible chat endpoint (Groq by default).

ClaimLens never relies on function calling: it asks for a JSON object and
validates it. Free-tier models occasionally return prose, <think> blocks,
truncated JSON or 429s, so every call goes through: primary model -> retry
with backoff -> fallback model -> caller-provided deterministic fallback.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Callable

from .config import settings

log = logging.getLogger("claimlens.llm")

_THINK = re.compile(r"<think>.*?</think>", re.S)


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response."""
    if not text:
        raise ValueError("empty response")
    t = _THINK.sub("", text).strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t.strip(), flags=re.M)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    start = t.find("{")
    if start < 0:
        raise ValueError("no JSON object in response")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(t)):
        ch = t[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(t[start:i + 1])
    raise ValueError("unterminated JSON object")


class LLM:
    def __init__(self, client=None, model: str | None = None, fallback_model: str | None = None):
        self.model = model or settings.llm_model
        fb = settings.llm_fallback_model if fallback_model is None else fallback_model
        self.fallback_models = [m.strip() for m in fb.split(",") if m.strip()]
        self._missing: set[str] = set()
        self.usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "failures": 0}
        if client is not None:
            self.client = client
        elif settings.fake_llm:
            from .fake_llm import FakeLLMClient

            self.client = FakeLLMClient()
            self.model = "offline-standin"
            self.fallback_models = []
        else:
            from openai import AsyncOpenAI

            self.client = AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key or "missing",
                                      max_retries=0, timeout=90)

    async def _once(self, model: str, messages: list[dict], max_tokens: int, json_mode: bool = True) -> dict:
        kwargs: dict[str, Any] = dict(model=model, messages=messages, temperature=0.1, max_tokens=max_tokens)
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if "gpt-oss" in model:
            kwargs["reasoning_effort"] = "low"
        try:
            resp = await self.client.chat.completions.create(**kwargs)
        except TypeError:  # client/SDK without reasoning_effort support
            kwargs.pop("reasoning_effort", None)
            resp = await self.client.chat.completions.create(**kwargs)
        self.usage["calls"] += 1
        u = getattr(resp, "usage", None)
        if u is not None:
            self.usage["prompt_tokens"] += getattr(u, "prompt_tokens", 0) or 0
            self.usage["completion_tokens"] += getattr(u, "completion_tokens", 0) or 0
        return extract_json(resp.choices[0].message.content or "")

    async def json(self, system: str, user: str, *, max_tokens: int = 1200,
                   validate: Callable[[dict], dict] | None = None,
                   fallback: Callable[[], dict] | None = None,
                   strict: bool = False) -> tuple[dict, str]:
        """Return (parsed_json, source) where source is the model name or 'fallback'.

        - 429 rate limits: wait (honouring Retry-After) and retry the same model,
          up to settings.llm_rate_limit_wait seconds per model (unlimited-ish in
          strict mode), because switching models mid-evaluation changes results.
        - 404 / model not found: skip that model immediately.
        - bad JSON / other errors: retry, alternating JSON mode, then next model.
        - strict=True never returns the deterministic fallback; it raises instead.
        """
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        last_err: Exception | None = None
        budget = settings.llm_rate_limit_wait * (10 if strict else 1)
        models = [self.model] + [m for m in self.fallback_models if m and m != self.model]
        for model in models:
            if model in self._missing:
                continue
            attempt, waited = 0, 0.0
            while attempt < 3:
                try:
                    data = await self._once(model, messages, max_tokens, json_mode=attempt % 2 == 0)
                    return (validate(data) if validate else data), model
                except Exception as e:  # noqa: BLE001 - we genuinely want to survive anything here
                    last_err = e
                    kind = _classify(e)
                    if kind == "missing":
                        self._missing.add(model)
                        log.warning("LLM model %s is not available on this account; skipping", model)
                        break
                    if kind == "rate_limit":
                        wait = _retry_after(e) or 5.0
                        if waited + wait > budget:
                            log.warning("LLM %s still rate-limited after %.0fs; trying next model", model, waited)
                            break
                        waited += wait
                        kind_msg = "daily token limit (TPD)" if "per day" in str(e).lower() else "rate limit"
                        log.warning("LLM %s hit %s; waiting %.0fs (%.0fs so far)", model, kind_msg, wait, waited)
                        await asyncio.sleep(wait)
                        continue  # rate limits don't count as attempts
                    attempt += 1
                    log.warning("LLM %s attempt %d failed: %s", model, attempt, str(e)[:160])
                    if attempt < 3:
                        await asyncio.sleep(min(2 ** attempt, 8))
        self.usage["failures"] += 1
        if fallback is not None and not strict:
            log.error("LLM unavailable, using deterministic fallback: %s", str(last_err)[:200])
            return fallback(), "fallback"
        raise RuntimeError(f"LLM failed: {last_err}")


def _classify(e: Exception) -> str:
    status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
    msg = str(e).lower()
    if status == 429 or "rate limit" in msg or "rate_limit" in msg:
        return "rate_limit"
    if status == 404 or "model_not_found" in msg or "does not exist" in msg or "decommissioned" in msg:
        return "missing"
    return "other"


_TRY_AGAIN = re.compile(r"try again in (?:(\d+)m)?([\d.]+)s", re.I)


def _retry_after(e: Exception) -> float | None:
    resp = getattr(e, "response", None)
    headers = getattr(resp, "headers", None) or {}
    try:
        v = headers.get("retry-after")
        if v:
            return min(float(v) + 0.5, 60.0)
    except (TypeError, ValueError):
        pass
    m = _TRY_AGAIN.search(str(e))  # Groq: "Please try again in 7.66s" / "in 1m2.5s"
    if m:
        return min(float(m.group(1) or 0) * 60 + float(m.group(2)) + 0.5, 60.0)
    return None
