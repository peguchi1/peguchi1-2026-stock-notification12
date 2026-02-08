from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class RulesConfig:
    rules: list[dict[str, Any]]

    @staticmethod
    def load(path: str | Path) -> "RulesConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        rules = data.get("rules", []) if isinstance(data, dict) else []
        return RulesConfig(rules=rules)

    def get_rule(self, rule_id: str) -> dict[str, Any]:
        for rule in self.rules:
            if rule.get("rule_id") == rule_id:
                return rule
        raise ValueError(f"Rule not found: {rule_id}")
