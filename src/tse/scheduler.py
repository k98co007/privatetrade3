from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from heapq import heappop, heappush


@dataclass(frozen=True, order=True)
class CandidateKey:
    occurred_at: datetime
    sequence: int
    watch_rank: int


@dataclass(frozen=True, order=True)
class BuyCandidate:
    key: CandidateKey
    symbol: str = field(compare=False)
    current_price: Decimal = field(compare=False)
    rebound_rate: Decimal = field(compare=False)


class SymbolScanScheduler:
    def __init__(self) -> None:
        self._heap: list[BuyCandidate] = []

    def enqueue_candidate(
        self,
        *,
        occurred_at: datetime,
        sequence: int,
        watch_rank: int,
        symbol: str,
        current_price: Decimal,
        rebound_rate: Decimal,
    ) -> None:
        heappush(
            self._heap,
            BuyCandidate(
                key=CandidateKey(
                    occurred_at=occurred_at,
                    sequence=sequence,
                    watch_rank=watch_rank,
                ),
                symbol=symbol,
                current_price=current_price,
                rebound_rate=rebound_rate,
            ),
        )

    def pop_next(self) -> BuyCandidate | None:
        if not self._heap:
            return None
        return heappop(self._heap)

    def clear(self) -> None:
        self._heap.clear()
