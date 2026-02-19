from __future__ import annotations

import json
import time
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .contracts import Mode, ServiceType
from .endpoint_resolver import CsmEndpointResolver
from .error_mapper import map_exception, map_http_status
from .errors import KiaError
from .idempotency import InMemoryIdempotencyStore
from .models import AccessToken
from .retry import execute_with_retry
from .token_provider import InMemoryTokenProvider

TransportFn = Callable[
    [str, str, dict[str, str], dict[str, Any] | None, dict[str, str] | None, float],
    tuple[int, dict[str, Any]],
]


def urllib_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None,
    query: dict[str, str] | None,
    timeout_seconds: float,
) -> tuple[int, dict[str, Any]]:
    final_url = url
    if query:
        final_url = f"{url}?{urlencode(query)}"

    encoded_payload: bytes | None = None
    if payload is not None:
        encoded_payload = json.dumps(payload).encode("utf-8")

    request = Request(url=final_url, data=encoded_payload, method=method)
    for key, value in headers.items():
        request.add_header(key, value)

    with urlopen(request, timeout=timeout_seconds) as response:
        status_code = int(response.getcode())
        raw = response.read().decode("utf-8")
        if not raw.strip():
            return status_code, {}
        return status_code, json.loads(raw)


class MockKiaApiClient:
    def call(
        self,
        *,
        service_type: ServiceType,
        mode: Mode | None,
        payload: dict[str, Any] | None,
        api_id: str | None = None,
        cont_yn: str = "N",
        next_key: str = "",
        idempotency_key: str | None = None,
        query: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if service_type == "auth":
            return self.auth_raw(mode=mode)
        if service_type == "quote":
            symbol = str((payload or {}).get("stk_cd") or "UNKNOWN")
            return self.fetch_quote_raw(mode=mode, symbol=symbol, api_id=api_id or "ka10007")
        if service_type == "chart":
            symbol = str((payload or {}).get("stk_cd") or "UNKNOWN")
            return {
                "stk_cd": symbol,
                "stk_min_pole_chart_qry": [
                    {
                        "cur_prc": "70000",
                        "cntr_tm": "20260219090300",
                    }
                ],
                "return_code": 0,
                "return_msg": "정상적으로 처리되었습니다",
            }
        if service_type == "order":
            return self.submit_order_raw(
                mode=mode,
                payload=payload or {},
                client_order_id=idempotency_key or "mock-order",
                api_id=api_id or "kt10000",
            )
        if service_type == "execution":
            current_query = query or {}
            return self.fetch_execution_raw(
                mode=mode,
                account_no=current_query.get("accountNo", "MOCK-ACCOUNT"),
                broker_order_id=current_query.get("brokerOrderId", "mock-order"),
            )
        raise map_http_status(500, {"service_type": service_type})

    def auth_raw(self, *, mode: Mode | None) -> dict[str, Any]:
        return {"access_token": "mock-token", "expires_in": 3600}

    def fetch_quote_raw(self, *, mode: Mode | None, symbol: str, api_id: str = "ka10007") -> dict[str, Any]:
        return {
            "symbol": symbol,
            "cur_prc": "70000",
            "sel_fpr_bid": "70000",
            "buy_fpr_bid": "69900",
            "price": "70000",
            "tick_size": 1,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "return_code": 0,
            "return_msg": "정상적으로 처리되었습니다",
        }

    def fetch_quotes_batch_raw(
        self,
        *,
        mode: Mode | None,
        symbols: list[str],
        timeout_ms: int,
        poll_cycle_id: str,
    ) -> dict[str, Any]:
        return {
            "poll_cycle_id": poll_cycle_id,
            "timeout_ms": timeout_ms,
            "quotes": [self.fetch_quote_raw(mode=mode, symbol=symbol) for symbol in symbols],
        }

    def submit_order_raw(
        self,
        *,
        mode: Mode | None,
        payload: dict[str, Any],
        client_order_id: str,
        api_id: str,
    ) -> dict[str, Any]:
        return {
            "broker_order_id": f"mock-{client_order_id}",
            "ord_no": f"mock-{client_order_id}",
            "client_order_id": client_order_id,
            "status": "ACCEPTED",
            "accepted_at": datetime.now(timezone.utc).isoformat(),
            "return_code": 0,
            "return_msg": "정상적으로 처리되었습니다",
            "echo": payload,
        }

    def fetch_execution_raw(self, *, mode: Mode | None, account_no: str, broker_order_id: str) -> dict[str, Any]:
        return {
            "broker_order_id": broker_order_id,
            "fills": [
                {
                    "execution_id": f"exe-{broker_order_id}",
                    "price": "70000",
                    "quantity": 1,
                    "executed_at": datetime.now(timezone.utc).isoformat(),
                }
            ],
            "remaining_qty": 0,
            "account_no": account_no,
        }

    def fetch_position_raw(self, *, mode: Mode | None, account_no: str, symbol: str | None) -> dict[str, Any]:
        positions = [
            {
                "account_no": account_no,
                "symbol": symbol or "005930",
                "quantity": 0,
                "avg_buy_price": "0",
            }
        ]
        return {"positions": positions}


class LiveKiaApiClient:
    def __init__(
        self,
        *,
        endpoint_resolver: CsmEndpointResolver,
        token_provider: InMemoryTokenProvider,
        transport: TransportFn = urllib_transport,
        timeout_seconds: float = 5.0,
        retry_attempts: int = 3,
        retry_base_delay_seconds: float = 0.2,
        retry_max_delay_seconds: float = 2.0,
        sleep_fn: Callable[[float], None] | None = None,
        rand_fn: Callable[[float, float], float] | None = None,
        monotonic_fn: Callable[[], float] | None = None,
        quote_min_interval_seconds: float = 0.25,
        idempotency_store: InMemoryIdempotencyStore | None = None,
    ) -> None:
        self._endpoint_resolver = endpoint_resolver
        self._token_provider = token_provider
        self._transport = transport
        self._timeout_seconds = timeout_seconds
        self._retry_attempts = retry_attempts
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._retry_max_delay_seconds = retry_max_delay_seconds
        self._sleep_fn = sleep_fn
        self._rand_fn = rand_fn
        self._monotonic_fn = monotonic_fn or time.monotonic
        self._quote_min_interval_seconds = max(0.0, quote_min_interval_seconds)
        self._quote_rate_lock = Lock()
        self._last_quote_sent_at: float | None = None
        self._idempotency_store = idempotency_store or InMemoryIdempotencyStore()

    def call(
        self,
        *,
        service_type: ServiceType,
        mode: Mode | None,
        payload: dict[str, Any] | None,
        api_id: str | None = None,
        cont_yn: str = "N",
        next_key: str = "",
        idempotency_key: str | None = None,
        query: dict[str, str] | None = None,
        retry_attempts_override: int | None = None,
    ) -> dict[str, Any]:
        resolved_mode: Mode = mode or "mock"
        if service_type == "auth":
            return self._send(
                service_type="auth",
                mode=resolved_mode,
                payload=payload,
                api_id=api_id,
                cont_yn=cont_yn,
                next_key=next_key,
                query=query,
                idempotency_key=idempotency_key,
            )

        has_forced_refresh = False

        def operation() -> dict[str, Any]:
            nonlocal has_forced_refresh
            token = self._token_provider.get_valid_token(resolved_mode)
            try:
                response = self._send(
                    service_type=service_type,
                    mode=resolved_mode,
                    payload=payload,
                    api_id=api_id,
                    cont_yn=cont_yn,
                    next_key=next_key,
                    query=query,
                    idempotency_key=idempotency_key,
                    token=token.token,
                )
                if service_type == "order" and idempotency_key:
                    self._idempotency_store.save(mode=resolved_mode, key=idempotency_key, response=response)
                return response
            except KiaError as exc:
                if exc.code == "KIA_AUTH_TOKEN_EXPIRED" and not has_forced_refresh:
                    has_forced_refresh = True
                    self._token_provider.invalidate(resolved_mode)
                    refreshed = self._token_provider.force_refresh(resolved_mode)
                    return self._send(
                        service_type=service_type,
                        mode=resolved_mode,
                        payload=payload,
                        api_id=api_id,
                        cont_yn=cont_yn,
                        next_key=next_key,
                        query=query,
                        idempotency_key=idempotency_key,
                        token=refreshed.token,
                    )
                if service_type == "order" and exc.code == "KIA_API_TIMEOUT":
                    existing = self._idempotency_store.find(mode=resolved_mode, key=idempotency_key)
                    if existing is not None:
                        return existing
                raise

        return execute_with_retry(
            operation,
            should_retry=lambda exc, _attempt: isinstance(exc, KiaError)
            and exc.retryable
            and getattr(exc, "code", "") != "KIA_AUTH_TOKEN_EXPIRED"
            and not (service_type == "order" and getattr(exc, "code", "") == "KIA_API_TIMEOUT"),
            attempts=retry_attempts_override if retry_attempts_override is not None else self._retry_attempts,
            base_delay_seconds=self._retry_base_delay_seconds,
            max_delay_seconds=self._retry_max_delay_seconds,
            sleep_fn=self._sleep_fn if self._sleep_fn is not None else __import__("time").sleep,
            rand_fn=self._rand_fn if self._rand_fn is not None else __import__("random").uniform,
        )

    def fetch_quote_raw(self, *, mode: Mode | None, symbol: str, api_id: str = "ka10007") -> dict[str, Any]:
        return self.call(service_type="quote", mode=mode, payload={"stk_cd": symbol}, api_id=api_id)

    def fetch_quotes_batch_raw(
        self,
        *,
        mode: Mode | None,
        symbols: list[str],
        timeout_ms: int,
        poll_cycle_id: str,
    ) -> dict[str, Any]:
        resolved_mode: Mode = mode or "mock"
        quotes: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for symbol in symbols:
            try:
                quote = self.call(
                    service_type="quote",
                    mode=resolved_mode,
                    payload={"stk_cd": symbol},
                    api_id="ka10007",
                    retry_attempts_override=1,
                )
                quotes.append(quote)
            except KiaError as first_error:
                if first_error.code in {"KIA_API_TIMEOUT", "KIA_RATE_LIMITED"}:
                    try:
                        quote = self.call(
                            service_type="quote",
                            mode=resolved_mode,
                            payload={"stk_cd": symbol},
                            api_id="ka10007",
                            retry_attempts_override=1,
                        )
                        quotes.append(quote)
                        continue
                    except KiaError as second_error:
                        errors.append(
                            {
                                "symbol": symbol,
                                "code": second_error.code,
                                "retryable": second_error.retryable,
                            }
                        )
                        continue
                errors.append(
                    {
                        "symbol": symbol,
                        "code": first_error.code,
                        "retryable": first_error.retryable,
                    }
                )
        return {
            "poll_cycle_id": poll_cycle_id,
            "timeout_ms": timeout_ms,
            "quotes": quotes,
            "errors": errors,
            "partial": len(errors) > 0,
        }

    def submit_order_raw(
        self,
        *,
        mode: Mode | None,
        payload: dict[str, Any],
        client_order_id: str,
        api_id: str,
    ) -> dict[str, Any]:
        return self.call(service_type="order", mode=mode, payload=payload, idempotency_key=client_order_id, api_id=api_id)

    def fetch_execution_raw(self, *, mode: Mode | None, account_no: str, broker_order_id: str) -> dict[str, Any]:
        return self.call(
            service_type="execution",
            mode=mode,
            payload=None,
            query={"accountNo": account_no, "brokerOrderId": broker_order_id},
        )

    def fetch_position_raw(self, *, mode: Mode | None, account_no: str, symbol: str | None) -> dict[str, Any]:
        query = {"accountNo": account_no}
        if symbol is not None:
            query["symbol"] = symbol
        return self.call(service_type="execution", mode=mode, payload=None, query=query)

    def _send(
        self,
        *,
        service_type: ServiceType,
        mode: Mode,
        payload: dict[str, Any] | None,
        api_id: str | None,
        cont_yn: str,
        next_key: str,
        query: dict[str, str] | None,
        idempotency_key: str | None,
        token: str | None = None,
    ) -> dict[str, Any]:
        request_guard = self._quote_rate_lock if service_type != "quote" else nullcontext()
        with request_guard:
            if service_type == "quote":
                self._enforce_quote_rate_limit()

            endpoint = self._endpoint_resolver.resolve(mode, service_type)
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "cont-yn": cont_yn,
                "next-key": next_key,
            }
            if token:
                headers["authorization"] = f"Bearer {token}"
            if api_id:
                headers["api-id"] = api_id
            if idempotency_key:
                headers["X-Idempotency-Key"] = idempotency_key

            try:
                status, response = self._transport(
                    endpoint.method,
                    f"{endpoint.base_url}{endpoint.path}",
                    headers,
                    payload,
                    query,
                    self._timeout_seconds,
                )
            except Exception as exc:  # pragma: no cover - mapper is covered
                raise map_exception(exc) from exc

        if status < 200 or status >= 300:
            raise map_http_status(status, response)
        if not isinstance(response, dict):
            raise map_exception(ValueError("response is not object"))
        return response

    def _enforce_quote_rate_limit(self) -> None:
        sleep_fn = self._sleep_fn if self._sleep_fn is not None else time.sleep
        with self._quote_rate_lock:
            if self._quote_min_interval_seconds <= 0:
                return
            now = self._monotonic_fn()
            if self._last_quote_sent_at is not None:
                elapsed = now - self._last_quote_sent_at
                remaining = self._quote_min_interval_seconds - elapsed
                if remaining > 0:
                    sleep_fn(remaining)
                    now = self._monotonic_fn()
            self._last_quote_sent_at = now


class RoutingKiaApiClient:
    def __init__(
        self,
        *,
        csm_repository: Any | None = None,
        transport: TransportFn = urllib_transport,
        timeout_seconds: float = 5.0,
        retry_attempts: int = 3,
        retry_base_delay_seconds: float = 0.2,
        retry_max_delay_seconds: float = 2.0,
        sleep_fn: Callable[[float], None] | None = None,
        rand_fn: Callable[[float, float], float] | None = None,
        monotonic_fn: Callable[[], float] | None = None,
        quote_min_interval_seconds: float = 0.25,
    ) -> None:
        self._resolver = CsmEndpointResolver(csm_repository=csm_repository)
        self._transport = transport
        self._mock_client = MockKiaApiClient()
        self._token_provider = InMemoryTokenProvider(self._issue_live_token)
        self._live_client = LiveKiaApiClient(
            endpoint_resolver=self._resolver,
            token_provider=self._token_provider,
            transport=transport,
            timeout_seconds=timeout_seconds,
            retry_attempts=retry_attempts,
            retry_base_delay_seconds=retry_base_delay_seconds,
            retry_max_delay_seconds=retry_max_delay_seconds,
            sleep_fn=sleep_fn,
            rand_fn=rand_fn,
            monotonic_fn=monotonic_fn,
            quote_min_interval_seconds=quote_min_interval_seconds,
        )
        self._last_mode: Mode | None = None

    def call(
        self,
        *,
        service_type: ServiceType,
        mode: Mode | None,
        payload: dict[str, Any] | None,
        api_id: str | None = None,
        cont_yn: str = "N",
        next_key: str = "",
        idempotency_key: str | None = None,
        query: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        selected_mode = self._resolve_mode(mode)
        client = self._select_client(selected_mode)
        return client.call(
            service_type=service_type,
            mode=selected_mode,
            payload=payload,
            api_id=api_id,
            cont_yn=cont_yn,
            next_key=next_key,
            idempotency_key=idempotency_key,
            query=query,
        )

    def auth_raw(self, *, mode: Mode | None) -> dict[str, Any]:
        return self.call(service_type="auth", mode=mode, payload=None)

    def fetch_quote_raw(self, *, mode: Mode | None, symbol: str, api_id: str = "ka10007") -> dict[str, Any]:
        return self.call(service_type="quote", mode=mode, payload={"stk_cd": symbol}, api_id=api_id)

    def fetch_quotes_batch_raw(
        self,
        *,
        mode: Mode | None,
        symbols: list[str],
        timeout_ms: int,
        poll_cycle_id: str,
    ) -> dict[str, Any]:
        selected_mode = self._resolve_mode(mode)
        client = self._select_client(selected_mode)
        return client.fetch_quotes_batch_raw(
            mode=selected_mode,
            symbols=symbols,
            timeout_ms=timeout_ms,
            poll_cycle_id=poll_cycle_id,
        )

    def submit_order_raw(
        self,
        *,
        mode: Mode | None,
        payload: dict[str, Any],
        client_order_id: str,
        api_id: str,
    ) -> dict[str, Any]:
        return self.call(service_type="order", mode=mode, payload=payload, idempotency_key=client_order_id, api_id=api_id)

    def fetch_execution_raw(self, *, mode: Mode | None, account_no: str, broker_order_id: str) -> dict[str, Any]:
        return self.call(
            service_type="execution",
            mode=mode,
            payload=None,
            query={"accountNo": account_no, "brokerOrderId": broker_order_id},
        )

    def fetch_position_raw(self, *, mode: Mode | None, account_no: str, symbol: str | None) -> dict[str, Any]:
        selected_mode = self._resolve_mode(mode)
        client = self._select_client(selected_mode)
        return client.fetch_position_raw(mode=selected_mode, account_no=account_no, symbol=symbol)

    def _resolve_mode(self, mode: Mode | None) -> Mode:
        if mode in {"mock", "live"}:
            selected_mode: Mode = mode
        else:
            selected_mode = self._resolver.read_csm_mode()
        if self._last_mode is not None and self._last_mode != selected_mode:
            self._token_provider.invalidate(self._last_mode)
        self._last_mode = selected_mode
        return selected_mode

    def _select_client(self, mode: Mode) -> MockKiaApiClient | LiveKiaApiClient:
        if mode == "mock":
            return self._mock_client
        if not self._resolver.has_live_credentials():
            return self._mock_client
        return self._live_client

    def _issue_live_token(self, mode: Mode) -> AccessToken:
        auth_payload = self._resolver.read_auth_payload()
        endpoint = self._resolver.resolve(mode, "auth")
        status, response = self._transport(
            endpoint.method,
            f"{endpoint.base_url}{endpoint.path}",
            {"Content-Type": "application/json;charset=UTF-8"},
            {"grant_type": "client_credentials", **auth_payload},
            None,
            5.0,
        )
        if status < 200 or status >= 300:
            raise map_http_status(status, response)

        token = str(response.get("token") or response.get("access_token") or "").strip()
        expires_in = int(response.get("expires_in", 3600))
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=expires_in)
        refresh_at = now + timedelta(seconds=max(expires_in - 60, 0))
        return AccessToken(token=token or "live-token", issued_at=now, expires_at=expires_at, refresh_at=refresh_at, mode=mode)
