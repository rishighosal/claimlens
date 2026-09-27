"""Check which chat models your LLM key can use, and that the configured ones answer.

Usage:  python scripts/check_llm.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from openai import AsyncOpenAI  # noqa: E402

from claimlens.config import settings  # noqa: E402


async def main() -> None:
    if not settings.llm_api_key:
        sys.exit("No GROQ_API_KEY / LLM_API_KEY in .env")
    client = AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
    models = sorted(m.id for m in (await client.models.list()).data)
    print(f"{len(models)} models available on {settings.llm_base_url}:")
    for m in models:
        print("  ", m)
    wanted = [settings.llm_model] + [m.strip() for m in settings.llm_fallback_model.split(",") if m.strip()]
    print("\nConfigured chain:")
    for m in wanted:
        if m not in models:
            print(f"   {m:40s} NOT AVAILABLE on this account")
            continue
        try:
            r = await client.chat.completions.create(
                model=m, messages=[{"role": "user", "content": 'Reply with the JSON {"ok": true}'}],
                max_tokens=200, response_format={"type": "json_object"})
            print(f"   {m:40s} OK -> {r.choices[0].message.content.strip()[:40]}")
        except Exception as e:  # noqa: BLE001
            print(f"   {m:40s} ERROR {str(e)[:120]}")


if __name__ == "__main__":
    asyncio.run(main())
