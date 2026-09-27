"""Runtime configuration, read once from the environment (and .env if present)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # optional dependency; plain env vars work without it
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # Hindsight
    hindsight_url: str = os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
    hindsight_api_key: str | None = os.getenv("HINDSIGHT_API_KEY") or None
    bank_id: str = os.getenv("CLAIMLENS_BANK_ID", "claimlens-siu")
    # Offline development only: an in-process stand-in for Hindsight so the UI
    # can be worked on without network access. Never used for the real demo.
    fake_memory: bool = _bool("CLAIMLENS_FAKE_MEMORY")

    # LLM (any OpenAI-compatible endpoint; Groq by default)
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    llm_api_key: str | None = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY") or None
    llm_model: str = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    llm_fallback_model: str = os.getenv("LLM_FALLBACK_MODEL", "qwen/qwen3-32b")
    fake_llm: bool = _bool("CLAIMLENS_FAKE_LLM")

    # Minimum cross-encoder relevance (0-1) for a "similar story" link
    narrative_min_rerank: float = float(os.getenv("CLAIMLENS_NARRATIVE_MIN_RERANK", "0.55"))

    # Data
    claims_path: Path = Path(os.getenv("CLAIMLENS_CLAIMS", str(DATA_DIR / "claims.json")))
    state_path: Path = Path(os.getenv("CLAIMLENS_STATE", str(DATA_DIR / "state.json")))


settings = Settings()
