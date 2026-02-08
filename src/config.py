from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AppConfig:
    raw: dict[str, Any]

    @staticmethod
    def load(path: str | Path) -> "AppConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return AppConfig(raw=data)

    def get(self, path: str, default: Any | None = None) -> Any:
        node: Any = self.raw
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def require(self, path: str) -> Any:
        value = self.get(path)
        if value is None:
            raise ValueError(f"Missing required config: {path}")
        return value