from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

ResultT = TypeVar("ResultT")


def execute_with_retry(
    operation: Callable[[], ResultT],
    *,
    should_retry: Callable[[Exception, int], bool],
    attempts: int = 3,
    base_delay_seconds: float = 0.2,
    max_delay_seconds: float = 2.0,
    sleep_fn: Callable[[float], None] = time.sleep,
    rand_fn: Callable[[float, float], float] = random.uniform,
) -> ResultT:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:  # pragma: no cover - behavior validated by tests
            last_error = exc
            if attempt >= attempts or not should_retry(exc, attempt):
                raise
            delay = min(base_delay_seconds * (2 ** (attempt - 1)), max_delay_seconds)
            jitter = rand_fn(0.0, 0.1)
            sleep_fn(delay + jitter)
    if last_error is None:
        raise RuntimeError("retry operation failed without explicit error")
    raise last_error
