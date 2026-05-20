"""처리 완료 글 ID 추적."""

from __future__ import annotations

import json
from pathlib import Path


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._ids: set[str] = set()
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._ids = set(data.get("processed_post_ids", []))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"processed_post_ids": sorted(self._ids)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_done(self, post_id: str) -> bool:
        return post_id in self._ids

    def mark_done(self, post_id: str) -> None:
        self._ids.add(post_id)
