"""Tiny JSON-file store for UI state (investigation results and decisions).

Hindsight is the memory; this file only remembers what the UI showed, so a
page reload doesn't lose the last investigation.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.data: dict[str, Any] = {"investigations": {}, "decisions": {}, "briefings": {}}
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text()))
            except json.JSONDecodeError:
                pass

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, default=str))
        tmp.replace(self.path)

    def put(self, section: str, key: str, value: Any) -> None:
        with self._lock:
            self.data.setdefault(section, {})[key] = value
            self._save()

    def get(self, section: str, key: str) -> Any:
        return self.data.get(section, {}).get(key)

    def section(self, section: str) -> dict:
        return self.data.get(section, {})

    def clear(self) -> None:
        with self._lock:
            self.data = {"investigations": {}, "decisions": {}, "briefings": {}}
            self._save()
