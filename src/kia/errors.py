from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class KiaErrorPayload:
    code: str
    message: str
    retryable: bool
    source: str = "KIA"
    details: dict[str, Any] | None = None


class KiaError(RuntimeError):
    def __init__(self, payload: KiaErrorPayload) -> None:
        super().__init__(f"{payload.code}: {payload.message}")
        self.payload = payload

    @property
    def code(self) -> str:
        return self.payload.code

    @property
    def retryable(self) -> bool:
        return self.payload.retryable


def make_kia_error(code: str, message: str, retryable: bool, details: dict[str, Any] | None = None) -> KiaError:
    return KiaError(KiaErrorPayload(code=code, message=message, retryable=retryable, details=details))
