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
        self.fallback_model = fallback_model or settings.llm_fallback_model
        self.usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "failures": 0}
        if client is not None:
            self.client = client
        elif settings.fake_llm:
            from .fake_llm import FakeLLMClient

            self.client = FakeLLMClient()
            self.model = self.fallback_model = "offline-standin"
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

    async def json(self, system: str, user: str, *, max_tokens: int = 1400,
                   validate: Callable[[dict], dict] | None = None,
                   fallback: Callable[[], dict] | None = None) -> tuple[dict, str]:
        """Return (parsed_json, source) where source is the model name or 'fallback'."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        last_err: Exception | None = None
        for model, attempts in ((self.model, 3), (self.fallback_model, 2)):
            for attempt in range(attempts):
                try:
                    # Alternate JSON mode off on retries: some models/providers reject
                    # json_object mode or fail its validation; lenient parsing covers us.
                    data = await self._once(model, messages, max_tokens, json_mode=attempt % 2 == 0)
                    return (validate(data) if validate else data), model
                except Exception as e:  # noqa: BLE001 - we genuinely want to survive anything here
                    last_err = e
                    wait = _retry_after(e) or min(2 ** attempt, 8)
                    log.warning("LLM %s attempt %d failed: %s", model, attempt + 1, str(e)[:200])
                    if attempt + 1 < attempts:
                        await asyncio.sleep(wait)
        self.usage["failures"] += 1
        if fallback is not None:
            log.error("LLM unavailable, using deterministic fallback: %s", last_err)
            return fallback(), "fallback"
        raise RuntimeError(f"LLM failed: {last_err}")


def _retry_after(e: Exception) -> float | None:
    resp = getattr(e, "response", None)
    headers = getattr(resp, "headers", None) or {}
    try:
        v = headers.get("retry-after")
        return min(float(v), 30.0) if v else None
    except (TypeError, ValueError):
        return None
