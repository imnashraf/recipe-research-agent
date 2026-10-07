"""Structured JSONL run log. Only ids, node names, counts and reasons; never page or comment text."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class RunLogger:
    def __init__(self, path: Path | None):
        self.path = path
        self._lock = threading.Lock()
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, **fields) -> None:
        if not self.path:
            return
        line = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event, **fields}
        with self._lock, open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
