from __future__ import annotations

import logging
from datetime import datetime, time as dt_time, timedelta, timezone
from decimal import Decimal, InvalidOperation
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


_LOGGER = logging.getLogger("privatetrade.kia.gateway")
_REFERENCE_MINUTE_START = dt_time(hour=9, minute=3, second=0)
_REFERENCE_MINUTE_END = dt_time(hour=9, minute=3, second=59)
_KST = timezone(timedelta(hours=9))


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _resolve_symbol(value: Any, *, fallback: str = "") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback.strip()


def _resolve_symbol_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _parse_non_negative_price(value: Any) -> Decimal:
    text = str(value).strip()
    if not text:
        return Decimal("0")
    return abs(Decimal(text.replace(",", "")))


def _is_negative_signed_price_text(value: Any) -> bool:
    text = str(value).strip()
    return bool(text) and text.lstrip().startswith("-")


def _parse_hhmmss(value: Any) -> dt_time | None:
    text = str(value).strip()
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) < 6:
        return None
    digits = digits[-6:]
    try:
        hour = int(digits[0:2])
        minute = int(digits[2:4])
        second = int(digits[4:6])
        return dt_time(hour=hour, minute=minute, second=second)
    except ValueError:
        return None


def _is_reference_minute(time_value: dt_time) -> bool:
    return _REFERENCE_MINUTE_START <= time_value <= _REFERENCE_MINUTE_END


class DefaultKiaGateway:
    def __init__(self, api_client: RoutingKiaApiClient | None = None, *, csm_repository: Any | None = None) -> None:
        self._api_client = api_client or RoutingKiaApiClient(csm_repository=csm_repository)

    def fetch_quote(self, req: FetchQuoteRequest) -> MarketQuote:
        raw = self._api_client.fetch_quote_raw(mode=req.mode, symbol=req.symbol, api_id="ka10007")
        price_value = raw.get("cur_prc", raw.get("price", "0"))
        try:
            normalized_price = _parse_non_negative_price(price_value)
        except (InvalidOperation, ValueError):
            _LOGGER.warning(
                "Invalid quote price format: symbol=%s raw_cur_prc=%s raw_price=%s mode=%s",
                req.symbol,
                raw.get("cur_prc"),
                raw.get("price"),
                req.mode,
            )
            normalized_price = Decimal("0")

        if _is_negative_signed_price_text(raw.get("cur_prc")) or _is_negative_signed_price_text(raw.get("price")):
            _LOGGER.warning(
                "Signed quote price detected: symbol=%s raw_cur_prc=%s raw_price=%s normalized=%s mode=%s",
                req.symbol,
                raw.get("cur_prc"),
                raw.get("price"),
                format(normalized_price, "f"),
                req.mode,
            )

        return MarketQuote(
            symbol=str(raw.get("symbol", req.symbol)),
            price=normalized_price,
            tick_size=int(raw.get("tick_size", 1)),
            as_of=_parse_dt(raw.get("as_of")),
            symbol_name=_resolve_symbol_name(
                raw.get(
                    "symbol_name",
                    raw.get(
                        "name",
                        raw.get(
                            "stk_nm",
                            raw.get("hts_kor_isnm", raw.get("prdt_abrv_name", raw.get("isu_nm"))),
                        ),
                    ),
                )
            ),
        )

    def fetch_reference_price_0903(self, *, mode: Mode | None, symbol: str) -> Decimal | None:
        base_dt = datetime.now(_KST).strftime("%Y%m%d")
        raw = self._api_client.call(
            service_type="chart",
            mode=mode,
            payload={
                "stk_cd": symbol,
                "tic_scope": "1",
                "upd_stkpc_tp": "1",
                "base_dt": base_dt,
            },
            api_id="ka10080",
        )
        rows = raw.get("stk_min_pole_chart_qry", [])
        if not isinstance(rows, list):
            return None

        best_time: dt_time | None = None
        best_price: Decimal | None = None

        for row in rows:
            if not isinstance(row, dict):
                continue
            trade_time = _parse_hhmmss(row.get("cntr_tm"))
            if trade_time is None or not _is_reference_minute(trade_time):
                continue

            try:
                normalized_price = _parse_non_negative_price(row.get("cur_prc", row.get("price", "0")))
            except (InvalidOperation, ValueError):
                continue
            if normalized_price <= 0:
                continue

            if best_time is None or trade_time > best_time:
                best_time = trade_time
                best_price = normalized_price

        if best_price is None:
            return None

        return best_price

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
        for index, item in enumerate(raw.get("quotes", [])):
            if not isinstance(item, dict):
                continue
            requested_symbol = req.symbols[index] if index < len(req.symbols) else ""
            resolved_symbol = _resolve_symbol(
                item.get("symbol", item.get("stk_cd", item.get("code", item.get("pdno", "")))),
                fallback=requested_symbol,
            )
            price_value = item.get("cur_prc", item.get("price", "0"))
            try:
                normalized_price = _parse_non_negative_price(price_value)
            except (InvalidOperation, ValueError):
                _LOGGER.warning(
                    "Invalid batch quote price format: cycle_id=%s symbol=%s raw_cur_prc=%s raw_price=%s mode=%s",
                    req.poll_cycle_id,
                    resolved_symbol,
                    item.get("cur_prc"),
                    item.get("price"),
                    req.mode,
                )
                normalized_price = Decimal("0")

            if _is_negative_signed_price_text(item.get("cur_prc")) or _is_negative_signed_price_text(item.get("price")):
                _LOGGER.warning(
                    "Signed batch quote price detected: cycle_id=%s symbol=%s raw_cur_prc=%s raw_price=%s normalized=%s mode=%s",
                    req.poll_cycle_id,
                    resolved_symbol,
                    item.get("cur_prc"),
                    item.get("price"),
                    format(normalized_price, "f"),
                    req.mode,
                )

            quotes.append(
                MarketQuote(
                    symbol=resolved_symbol,
                    price=normalized_price,
                    tick_size=int(item.get("tick_size", 1)),
                    as_of=_parse_dt(item.get("as_of")),
                    symbol_name=_resolve_symbol_name(
                        item.get(
                            "symbol_name",
                            item.get(
                                "name",
                                item.get(
                                    "stk_nm",
                                    item.get("hts_kor_isnm", item.get("prdt_abrv_name", item.get("isu_nm"))),
                                ),
                            ),
                        )
                    ),
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
