import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

# Tests never touch the network.
os.environ.setdefault("CLAIMLENS_FAKE_MEMORY", "1")
os.environ.setdefault("CLAIMLENS_FAKE_LLM", "1")
os.environ.setdefault("CLAIMLENS_STATE", str(ROOT / "data" / "test_state.json"))
