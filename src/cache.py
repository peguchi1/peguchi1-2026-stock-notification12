from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class FileCache:
    def __init__(self, root: Path, ttl_seconds: int) -> None:
        self.root = root
        self.ttl_seconds = ttl_seconds
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace(":", "_")
        return self.root / f"{safe}.json"

    def get(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - payload.get("ts", 0) > self.ttl_seconds:
                return None
            return payload.get("value")
        except Exception:
            return None

    def set(self, key: str, value: Any) -> None:
        path = self._path(key)
        payload = {"ts": time.time(), "value": value}
        path.write_text(json.dumps(payload), encoding="utf-8")