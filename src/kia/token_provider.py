from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Callable

from .contracts import Mode
from .models import AccessToken


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryTokenProvider:
    def __init__(
        self,
        auth_issuer: Callable[[Mode], AccessToken],
        *,
        now_fn: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._auth_issuer = auth_issuer
        self._now_fn = now_fn
        self._cache: dict[Mode, AccessToken] = {}
        self._locks: dict[Mode, Lock] = {
            "mock": Lock(),
            "live": Lock(),
        }

    def get_valid_token(self, mode: Mode) -> AccessToken:
        token = self._cache.get(mode)
        now = self._now_fn()
        if token is not None and now < token.refresh_at:
            return token
        with self._locks[mode]:
            token = self._cache.get(mode)
            now = self._now_fn()
            if token is not None and now < token.refresh_at:
                return token
            refreshed = self._auth_issuer(mode)
            self._cache[mode] = refreshed
            return refreshed

    def force_refresh(self, mode: Mode) -> AccessToken:
        with self._locks[mode]:
            refreshed = self._auth_issuer(mode)
            self._cache[mode] = refreshed
            return refreshed

    def invalidate(self, mode: Mode) -> None:
        self._cache.pop(mode, None)
