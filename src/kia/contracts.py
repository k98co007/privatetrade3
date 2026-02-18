from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol

Mode = Literal["mock", "live"]
ServiceType = Literal["auth", "quote", "order", "execution"]


@dataclass(frozen=True)
class FetchQuoteRequest:
    mode: Mode | None
    symbol: str


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    price: Decimal
    tick_size: int
    as_of: datetime


@dataclass(frozen=True)
class SubmitOrderRequest:
    mode: Mode | None
    account_no: str
    symbol: str
    side: Literal["BUY", "SELL"]
    order_type: Literal["LIMIT", "MARKET"]
    price: Decimal | None
    quantity: int
    client_order_id: str


@dataclass(frozen=True)
class OrderResult:
    broker_order_id: str
    client_order_id: str
    status: Literal["ACCEPTED", "REJECTED", "PENDING"]
    accepted_at: datetime | None


@dataclass(frozen=True)
class FetchExecutionRequest:
    mode: Mode | None
    account_no: str
    broker_order_id: str


@dataclass(frozen=True)
class ExecutionFill:
    execution_id: str
    price: Decimal
    quantity: int
    executed_at: datetime


@dataclass(frozen=True)
class ExecutionResult:
    broker_order_id: str
    fills: list[ExecutionFill]
    remaining_qty: int


@dataclass(frozen=True)
class FetchPositionRequest:
    mode: Mode | None
    account_no: str
    symbol: str | None = None


@dataclass(frozen=True)
class PositionSnapshot:
    account_no: str
    symbol: str
    quantity: int
    avg_buy_price: Decimal


@dataclass(frozen=True)
class PollQuotesRequest:
    mode: Mode | None
    symbols: list[str]
    poll_cycle_id: str
    timeout_ms: int


@dataclass(frozen=True)
class PollQuoteError:
    symbol: str
    code: str
    retryable: bool


@dataclass(frozen=True)
class PollQuotesResult:
    poll_cycle_id: str
    quotes: list[MarketQuote]
    errors: list[PollQuoteError]
    partial: bool


class KiaApiClient(Protocol):
    def call(
        self,
        *,
        service_type: ServiceType,
        mode: Mode | None,
        payload: dict[str, Any] | None,
        api_id: str | None = None,
        cont_yn: Literal["N", "Y"] = "N",
        next_key: str = "",
        idempotency_key: str | None = None,
        query: dict[str, str] | None = None,
    ) -> dict[str, Any]: ...

    def auth_raw(self, *, mode: Mode | None) -> dict[str, Any]: ...

    def fetch_quote_raw(self, *, mode: Mode | None, symbol: str, api_id: str = "ka10007") -> dict[str, Any]: ...

    def fetch_quotes_batch_raw(
        self,
        *,
        mode: Mode | None,
        symbols: list[str],
        timeout_ms: int,
        poll_cycle_id: str,
    ) -> dict[str, Any]: ...

    def submit_order_raw(
        self,
        *,
        mode: Mode | None,
        payload: dict[str, Any],
        client_order_id: str,
        api_id: str,
    ) -> dict[str, Any]: ...

    def fetch_execution_raw(self, *, mode: Mode | None, account_no: str, broker_order_id: str) -> dict[str, Any]: ...

    def fetch_position_raw(self, *, mode: Mode | None, account_no: str, symbol: str | None) -> dict[str, Any]: ...


class KiaGateway(Protocol):
    def fetch_quote(self, req: FetchQuoteRequest) -> MarketQuote: ...

    def fetch_quotes_batch(self, req: PollQuotesRequest) -> PollQuotesResult: ...

    def submit_order(self, req: SubmitOrderRequest) -> OrderResult: ...

    def fetch_execution(self, req: FetchExecutionRequest) -> ExecutionResult: ...

    def fetch_position(self, req: FetchPositionRequest) -> list[PositionSnapshot]: ...
