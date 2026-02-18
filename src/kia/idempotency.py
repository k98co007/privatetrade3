from __future__ import annotations

from threading import Lock
from typing import Any

from .contracts import Mode


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._store: dict[tuple[Mode, str], dict[str, Any]] = {}

    def save(self, *, mode: Mode, key: str, response: dict[str, Any]) -> None:
        if not key:
            return
        with self._lock:
            self._store[(mode, key)] = dict(response)

    def find(self, *, mode: Mode, key: str | None) -> dict[str, Any] | None:
        if not key:
            return None
        with self._lock:
            response = self._store.get((mode, key))
            return dict(response) if response is not None else None
