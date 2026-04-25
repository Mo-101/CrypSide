"""
g4_whitelist_gate.py
Read-only whitelist gate for G4. Loads whitelist.json and answers is_allowed() by pocket identity.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class PocketKey:
    policy: str
    regime: str
    side: str

    @property
    def pocket_id(self) -> str:
        return f"{self.policy}|{self.regime}|{self.side}"


class WhitelistGate:
    """Loads whitelist.json once, answers O(1) membership queries.
    Use reload() to pick up updates without restarting the scanner."""

    def __init__(self, whitelist_path: str | Path):
        self.whitelist_path = Path(whitelist_path)
        self._payload: Dict = {}
        self._index: Dict[str, Dict] = {}
        self.reload()

    def reload(self) -> None:
        self._payload = json.loads(self.whitelist_path.read_text(encoding="utf-8"))
        self._index = {
            pocket["pocket_id"]: pocket
            for pocket in self._payload.get("pockets", [])
        }

    @property
    def size(self) -> int:
        return len(self._index)

    def is_allowed(self, policy: str, regime: str, side: str) -> bool:
        key = PocketKey(policy=policy, regime=regime, side=side.upper())
        return key.pocket_id in self._index

    def get_meta(self, policy: str, regime: str, side: str) -> Optional[Dict]:
        key = PocketKey(policy=policy, regime=regime, side=side.upper())
        return self._index.get(key.pocket_id)

    def all_pocket_ids(self) -> list[str]:
        return list(self._index.keys())
