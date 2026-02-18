from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .api_client import RoutingKiaApiClient
from .contracts import (
    ExecutionFill,
    ExecutionResult,
    FetchExecutionRequest,
    FetchPositionRequest,
    FetchQuoteRequest,
    MarketQuote,
    Mode,
    OrderResult,
    PollQuoteError,
    PollQuotesRequest,
    PollQuotesResult,
    PositionSnapshot,
    SubmitOrderRequest,
)
from .errors import make_kia_error


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


class DefaultKiaGateway:
    def __init__(self, api_client: RoutingKiaApiClient | None = None, *, csm_repository: Any | None = None) -> None:
        self._api_client = api_client or RoutingKiaApiClient(csm_repository=csm_repository)

    def fetch_quote(self, req: FetchQuoteRequest) -> MarketQuote:
        raw = self._api_client.fetch_quote_raw(mode=req.mode, symbol=req.symbol, api_id="ka10007")
        price_value = raw.get("cur_prc", raw.get("price", "0"))
        return MarketQuote(
            symbol=str(raw.get("symbol", req.symbol)),
            price=Decimal(str(price_value)),
            tick_size=int(raw.get("tick_size", 1)),
            as_of=_parse_dt(raw.get("as_of")),
        )

    def fetch_quotes_batch(self, req: PollQuotesRequest) -> PollQuotesResult:
        if not (1 <= len(req.symbols) <= 20):
            raise make_kia_error("KIA_INVALID_REQUEST", "symbols는 1개 이상 20개 이하여야 합니다.", False)
        if not req.poll_cycle_id.strip():
            raise make_kia_error("KIA_INVALID_REQUEST", "poll_cycle_id는 빈 문자열일 수 없습니다.", False)

        raw = self._api_client.fetch_quotes_batch_raw(
            mode=req.mode,
            symbols=req.symbols,
            timeout_ms=req.timeout_ms,
            poll_cycle_id=req.poll_cycle_id,
        )

        quotes: list[MarketQuote] = []
        for item in raw.get("quotes", []):
            if not isinstance(item, dict):
                continue
            price_value = item.get("cur_prc", item.get("price", "0"))
            quotes.append(
                MarketQuote(
                    symbol=str(item.get("symbol", "")),
                    price=Decimal(str(price_value)),
                    tick_size=int(item.get("tick_size", 1)),
                    as_of=_parse_dt(item.get("as_of")),
                )
            )

        errors: list[PollQuoteError] = []
        for item in raw.get("errors", []):
            if not isinstance(item, dict):
                continue
            errors.append(
                PollQuoteError(
                    symbol=str(item.get("symbol", "")),
                    code=str(item.get("code", "KIA_UNKNOWN")),
                    retryable=bool(item.get("retryable", False)),
                )
            )

        return PollQuotesResult(
            poll_cycle_id=str(raw.get("poll_cycle_id", req.poll_cycle_id)),
            quotes=quotes,
            errors=errors,
            partial=bool(raw.get("partial", len(errors) > 0)),
        )

    def submit_order(self, req: SubmitOrderRequest) -> OrderResult:
        if req.order_type == "MARKET":
            trde_tp = "3"
        else:
            trde_tp = "0"
        api_id = "kt10000" if req.side == "BUY" else "kt10001"
        payload = {
            "dmst_stex_tp": "KRX",
            "stk_cd": req.symbol,
            "ord_qty": str(req.quantity),
            "ord_uv": "" if req.price is None else str(req.price),
            "trde_tp": trde_tp,
            "cond_uv": "",
        }
        raw = self._api_client.submit_order_raw(
            mode=req.mode,
            payload=payload,
            client_order_id=req.client_order_id,
            api_id=api_id,
        )
        accepted_at = raw.get("accepted_at")
        return OrderResult(
            broker_order_id=str(raw.get("ord_no", raw.get("broker_order_id", ""))),
            client_order_id=str(raw.get("client_order_id", req.client_order_id)),
            status=str(raw.get("status", "PENDING")),  # type: ignore[arg-type]
            accepted_at=_parse_dt(accepted_at) if accepted_at else None,
        )

    def fetch_execution(self, req: FetchExecutionRequest) -> ExecutionResult:
        raw = self._api_client.fetch_execution_raw(
            mode=req.mode,
            account_no=req.account_no,
            broker_order_id=req.broker_order_id,
        )
        fills: list[ExecutionFill] = []
        for item in raw.get("fills", []):
            fills.append(
                ExecutionFill(
                    execution_id=str(item.get("execution_id", "")),
                    price=Decimal(str(item.get("price", "0"))),
                    quantity=int(item.get("quantity", 0)),
                    executed_at=_parse_dt(item.get("executed_at")),
                )
            )

        return ExecutionResult(
            broker_order_id=str(raw.get("broker_order_id", req.broker_order_id)),
            fills=fills,
            remaining_qty=int(raw.get("remaining_qty", 0)),
        )

    def fetch_position(self, req: FetchPositionRequest) -> list[PositionSnapshot]:
        raw = self._api_client.fetch_position_raw(mode=req.mode, account_no=req.account_no, symbol=req.symbol)
        rows = raw.get("positions", [])
        if not isinstance(rows, list):
            return []

        snapshots: list[PositionSnapshot] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            snapshots.append(
                PositionSnapshot(
                    account_no=str(item.get("account_no", req.account_no)),
                    symbol=str(item.get("symbol", "")),
                    quantity=int(item.get("quantity", 0)),
                    avg_buy_price=Decimal(str(item.get("avg_buy_price", "0"))),
                )
            )
        return snapshots
