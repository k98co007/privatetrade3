# ILD-OPM v0.1.0

- 문서명: OPM 모듈 구현 상세 설계서 (ILD)
- 버전: v0.1.0
- 작성일: 2026-02-17
- 기반 문서:
  - `docs/lld/LLD-OPM-v0.1.0.md`
  - `docs/lld/LLD-KIA-v0.1.0.md`
  - `docs/lld/LLD-PRP-v0.1.0.md`
  - `docs/hld/HLD-v0.1.0.md`
  - `docs/srs/SRS-v0.1.0.md`
- 모듈: `OPM` (Order & Position Manager)
- 언어/런타임 가정: Python 3.12+, Decimal 기반 계산, 동기 서비스 + 백그라운드 정합 워커

## 1. 구현 범위

LLD-OPM의 주문/체결/포지션 책임을 실제 코드 단위로 구체화한다.

- 주문 수명주기 상태머신 및 상태 전이 핸들러 구현
- 매수/매도 지정가 계산(현재가+2틱, 현재가-2틱) 유틸 함수 구현
- 체결 멱등 처리 및 주문 정합(Reconciliation) 알고리즘 구현
- PRP 이벤트/스냅샷 저장 오케스트레이션 구현
- 복구 모드 진입/해제 및 신규 주문 차단 가드 구현
- OPM 표준 예외 및 재시도 가능성 계약 정의
- TSE 시세 루프 저하(`DEGRADED`) 시 연동 안전 규칙 적용

비범위:
- 전략 신호 생성(TSE)
- 브로커 HTTP/토큰 상세 구현(KIA)
- 리포트 집계(PRP)

## 2. 디렉터리/모듈 레이아웃 제안

```text
src/
  opm/
    __init__.py
    bootstrap.py

    domain/
      __init__.py
      enums.py                    # OrderStatus, PositionState, ReconcileState
      models.py                   # OrderAggregate, PositionModel, ExecutionFill
      state_machine.py            # 상태 전이 검증기 + 전이 함수
    tick_rules.py               # KOSPI tick resolver, align, buy/sell price calc
      calculators.py              # qty/pnl/fee/tax 계산 유틸
      idempotency.py              # clientOrderId, executionId ledger

    dto/
      __init__.py
      command_dto.py              # PlaceBuyOrderCommand, PlaceSellOrderCommand
      event_dto.py                # OpmOrderEvent, OpmExecutionEvent, OpmPositionSnapshot
      reconcile_dto.py            # ReconcileTask, ReconcileResult, ReconcileMismatch
      error_dto.py                # OpmErrorContract

    service/
      __init__.py
      order_service.py            # place_buy_order, place_sell_order
      execution_service.py        # apply_execution_result
      reconcile_service.py        # start_reconciliation, run_once
      recovery_service.py         # recover_on_startup
      publish_service.py          # PRP 저장 호출 래퍼 + 재시도

    gateway/
      __init__.py
      kia_gateway.py              # submitOrder/fetchExecution/fetchPosition 추상화
      prp_gateway.py              # saveOrderEvent/saveExecutionEvent/savePositionSnapshot

    infra/
      __init__.py
      memory_queue.py             # PRP write-fail 임시 큐
      lock_manager.py             # 종목 단위 락
      clock.py

    errors/
      __init__.py
      exceptions.py               # OPM 예외 계층
      contracts.py                # code, retryable, severity 매핑

tests/
  opm/
    test_tick_rules.py
    test_state_machine.py
    test_idempotency.py
    test_reconciliation.py
    test_recovery.py
```

## 3. 타입 및 메서드 시그니처

## 3.1 공통 타입

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol

Side = Literal["BUY", "SELL"]
OrderType = Literal["LIMIT"]
OrderStatus = Literal[
    "PENDING_SUBMIT",
    "SUBMITTED",
    "ACCEPTED",
    "PARTIALLY_FILLED",
    "FILLED",
    "REJECTED",
    "CANCELED",
    "RECONCILING",
]
PositionState = Literal["FLAT", "LONG_OPEN", "EXITING", "CLOSED"]
```

## 3.2 Command / Aggregate / Event DTO

```python
@dataclass(frozen=True)
class PlaceBuyOrderCommand:
    command_id: str
    trading_date: date
    symbol: str
    side: Literal["BUY"]
    budget: Decimal
    current_price: Decimal
    requested_at: datetime

@dataclass(frozen=True)
class PlaceSellOrderCommand:
    command_id: str
    trading_date: date
    symbol: str
    side: Literal["SELL"]
    current_price: Decimal
    requested_at: datetime

@dataclass
class OrderAggregate:
    order_aggregate_id: str
    trading_date: date
    symbol: str
    side: Side
    order_type: OrderType
    requested_price: Decimal
    requested_qty: int
    status: OrderStatus
    broker_order_id: str | None
    client_order_id: str
    cum_executed_qty: int
    avg_executed_price: Decimal
    remaining_qty: int
    last_error_code: str | None
    last_updated_at: datetime

@dataclass
class PositionModel:
    position_id: str
    trading_date: date
    symbol: str
    state: PositionState
    quantity: int
    avg_buy_price: Decimal
    buy_notional: Decimal
    sell_quantity: int
    avg_sell_price: Decimal
    sell_notional: Decimal
    current_price: Decimal
    gross_interim_pnl: Decimal
    estimated_sell_tax: Decimal
    estimated_sell_fee: Decimal
    net_interim_pnl: Decimal
    current_profit_rate: Decimal
    max_profit_rate: Decimal
    min_profit_locked: bool
    state_version: int
    updated_at: datetime

@dataclass(frozen=True)
class ExecutionFill:
    execution_id: str
    broker_order_id: str
    symbol: str
    side: Side
    price: Decimal
    qty: int
    executed_at: datetime
```

## 3.3 OPM 서비스 인터페이스

```python
class OrderService(Protocol):
    def place_buy_order(self, command: PlaceBuyOrderCommand) -> OrderAggregate: ...
    def place_sell_order(self, command: PlaceSellOrderCommand) -> OrderAggregate: ...

class ExecutionService(Protocol):
    def apply_execution_result(
        self,
        order: OrderAggregate,
        fills: list[ExecutionFill],
        broker_remaining_qty: int,
        latest_market_price: Decimal,
    ) -> tuple[OrderAggregate, PositionModel]: ...

class ReconcileService(Protocol):
    def start_reconciliation(self, order: OrderAggregate, reason_code: str) -> None: ...
    def run_reconcile_once(self, trading_date: date, symbol: str) -> None: ...
    def run_reconcile_batch(self, max_batch_size: int = 100) -> int: ...

class RecoveryService(Protocol):
    def begin_recovery_mode(self, trading_date: date) -> None: ...
    def recover_on_startup(self, trading_date: date) -> None: ...
    def finish_recovery_mode(self, trading_date: date) -> None: ...
```

## 3.4 외부 게이트웨이 인터페이스

```python
class KiaGateway(Protocol):
    def submit_order(self, *, client_order_id: str, symbol: str, side: Side, price: Decimal, qty: int, order_type: OrderType) -> dict: ...
    def fetch_execution(self, *, broker_order_id: str | None = None, client_order_id: str | None = None) -> dict: ...
    def fetch_position(self, *, symbol: str) -> dict: ...
    def realtime_login(self, *, mode: str | None) -> dict: ...
    def realtime_register(self, req) -> dict: ...
    def realtime_receive(self, *, mode: str | None) -> dict: ...
    def realtime_remove(self, req) -> dict: ...
    def realtime_close(self, *, mode: str | None) -> None: ...

class PrpGateway(Protocol):
    def save_order_event(self, event: dict) -> None: ...
    def save_execution_event(self, event: dict) -> bool: ...
    def save_position_snapshot(self, snapshot: dict) -> None: ...
    def find_latest_snapshot(self, trading_date: date, symbol: str) -> dict | None: ...
```

### 3.4.1 실시간 실행 경로(코드 1:1)

OPM은 KIA 실시간 체결/잔고 구독을 아래 순서로 호출한다.

1) `OpmService.open_realtime_execution_stream(mode)`  
2) `KiaGateway.realtime_login(mode)`  
3) `KiaGateway.realtime_register(00/04, grp_no=1)`  
4) `OpmService.poll_realtime_execution_event(mode)` -> `KiaGateway.realtime_receive(mode)`  
5) `OpmService.close_realtime_execution_stream(mode)` -> `KiaGateway.realtime_remove(...)` -> `KiaGateway.realtime_close(mode)`

기본 구독 타입은 `00(주문체결)`, `04(잔고)`로 고정한다.

책임 경계:
- 이 경로의 `realtime_receive`는 OPM의 체결/잔고 동기화 입력 전용이다.
- 전략용 호가 모니터링(`QuoteEvent`)은 TSE의 `fetch_quotes_batch` 경로에서 생성되며 OPM 경로에서 생성/판정하지 않는다.

### 3.4.2 실시간 수신 파싱/반영 경로(코드 1:1)

수신 이벤트는 아래 메서드 체인으로 즉시 반영한다.

1) `OpmService.poll_and_apply_realtime_execution_event(mode, order, position)`  
2) `OpmService.apply_realtime_execution_event(raw_event, order, position)`  
3) `type="00"`이면 `OpmService._apply_realtime_order_execution_values(...)`  
4) `type="04"`이면 `OpmService._apply_realtime_balance_values(...)`

핵심 FID 매핑 규칙:

- `00`: `9203(주문번호)`, `9001(종목코드)`, `907(매도수구분)`, `908(체결시각)`, `909(체결번호)`, `910(체결가)`, `911(체결량)`, `902(미체결수량)`, `10(현재가)`
- `04`: `930(보유수량)`, `931(매입단가)`, `10(현재가)`

`00` 반영 시 `ExecutionFill`로 변환 후 `reconcile_execution_events`를 호출하고, `04` 반영 시 `PositionModel`을 즉시 갱신한 뒤 스냅샷을 저장한다.

추적성(Observability) 규칙:

- `00` 수신마다 PRP `strategy_events`에 `OPM_REALTIME_00_RECEIVED`를 기록한다.
- `04` 수신마다 PRP `strategy_events`에 `OPM_REALTIME_04_RECEIVED`를 기록한다.
- 로그 payload는 체결/잔고 반영에 필요한 최소 필드만 저장하고, 계좌번호 등 민감 필드는 저장하지 않는다.

예외 처리 경계:
- `type=00/04` 외 이벤트는 v0.1.0에서 무시하거나 상위 관측 로그로만 남기고, 주문/포지션 상태에는 반영하지 않는다.

## 4. 상태 전이 핸들러 설계

## 4.1 주문 상태 전이 함수 시그니처

```python
def on_submit_requested(order: OrderAggregate, now: datetime) -> OrderAggregate: ...
def on_submit_accepted(order: OrderAggregate, broker_order_id: str, now: datetime) -> OrderAggregate: ...
def on_submit_rejected(order: OrderAggregate, reason_code: str, now: datetime) -> OrderAggregate: ...
def on_submit_timeout(order: OrderAggregate, now: datetime) -> OrderAggregate: ...
def on_partial_fill(order: OrderAggregate, fill_qty: int, fill_price: Decimal, now: datetime) -> OrderAggregate: ...
def on_full_fill(order: OrderAggregate, now: datetime) -> OrderAggregate: ...
def on_cancel_confirmed(order: OrderAggregate, now: datetime) -> OrderAggregate: ...
def on_reconcile_resolved(order: OrderAggregate, resolved_status: OrderStatus, now: datetime) -> OrderAggregate: ...
```

## 4.2 전이 검증 규칙

```python
ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    "PENDING_SUBMIT": {"SUBMITTED"},
    "SUBMITTED": {"ACCEPTED", "REJECTED", "RECONCILING"},
    "ACCEPTED": {"PARTIALLY_FILLED", "FILLED", "CANCELED", "RECONCILING"},
    "PARTIALLY_FILLED": {"FILLED", "CANCELED", "RECONCILING"},
    "RECONCILING": {"ACCEPTED", "PARTIALLY_FILLED", "FILLED", "REJECTED"},
    "FILLED": set(),
    "REJECTED": set(),
    "CANCELED": set(),
}


def transition_order_status(order: OrderAggregate, next_status: OrderStatus, now: datetime) -> OrderAggregate:
    if next_status not in ALLOWED_TRANSITIONS[order.status]:
        raise OpmInvalidStateTransitionError(
            current_state=order.status,
            target_state=next_status,
            order_aggregate_id=order.order_aggregate_id,
        )
    order.status = next_status
    order.last_updated_at = now
    return order
```

## 4.3 포지션 상태 핸들러

```python
def on_buy_fill(position: PositionModel, fill_price: Decimal, fill_qty: int, now: datetime) -> PositionModel: ...
def on_sell_order_submitted(position: PositionModel, now: datetime) -> PositionModel: ...
def on_sell_fill(position: PositionModel, fill_price: Decimal, fill_qty: int, now: datetime) -> PositionModel: ...
def on_sell_order_canceled_or_rejected(position: PositionModel, remain_qty: int, now: datetime) -> PositionModel: ...
```

포지션 전이 규칙:
- `FLAT -> LONG_OPEN`: BUY 체결수량 누적 > 0
- `LONG_OPEN -> EXITING`: SELL 주문 `SUBMITTED/ACCEPTED`
- `EXITING -> CLOSED`: SELL 누적체결수량 == 보유수량
- `EXITING -> LONG_OPEN`: SELL 취소/거부 + 잔여 보유수량 > 0

## 5. 틱 사이즈 유틸리티 함수 설계

## 5.1 함수 시그니처

```python
def resolve_kospi_tick(price: Decimal) -> Decimal: ...
def resolve_tick_size(current_price: Decimal, market: str = "KOSPI", tick_size_from_quote: Decimal | None = None) -> Decimal: ...
def align_to_tick(price: Decimal, tick: Decimal, direction: Literal["down", "up"]) -> Decimal: ...
def calc_sell_limit_price(current_price: Decimal, tick_size_from_quote: Decimal | None = None) -> Decimal: ...
```

## 5.2 구현 계약

```python
from decimal import Decimal, ROUND_DOWN, ROUND_UP

ZERO = Decimal("0")


def resolve_kospi_tick(price: Decimal) -> Decimal:
    if price <= ZERO:
        raise OpmInvalidMarketPriceError(value=price)
    if price < Decimal("1000"):
        return Decimal("1")
    if price < Decimal("5000"):
        return Decimal("5")
    if price < Decimal("10000"):
        return Decimal("10")
    if price < Decimal("50000"):
        return Decimal("50")
    if price < Decimal("100000"):
        return Decimal("100")
    if price < Decimal("500000"):
        return Decimal("500")
    return Decimal("1000")


def resolve_tick_size(current_price: Decimal, market: str = "KOSPI", tick_size_from_quote: Decimal | None = None) -> Decimal:
    if tick_size_from_quote is not None:
        if tick_size_from_quote <= ZERO:
            raise OpmInvalidTickSizeError(value=tick_size_from_quote)
        return tick_size_from_quote
    if market != "KOSPI":
        raise OpmUnsupportedMarketError(market=market)
    return resolve_kospi_tick(current_price)


def align_to_tick(price: Decimal, tick: Decimal, direction: Literal["down", "up"]) -> Decimal:
    if price <= ZERO:
        raise OpmInvalidSellPriceError(value=price)
    if tick <= ZERO:
        raise OpmInvalidTickSizeError(value=tick)
    units = price / tick
    if direction == "down":
        return units.to_integral_value(rounding=ROUND_DOWN) * tick
    if direction == "up":
        return units.to_integral_value(rounding=ROUND_UP) * tick
    raise OpmValidationError(code="OPM_ALIGN_DIRECTION_INVALID", detail=f"direction={direction}")


def calc_sell_limit_price(current_price: Decimal, tick_size_from_quote: Decimal | None = None) -> Decimal:
    tick = resolve_tick_size(current_price=current_price, tick_size_from_quote=tick_size_from_quote)
    raw_sell_price = current_price - (Decimal("2") * tick)
    sell_price = align_to_tick(raw_sell_price, tick, "down")
    if sell_price <= ZERO:
        raise OpmInvalidSellPriceError(value=sell_price)
    return sell_price
```

## 6. 주문/체결 오케스트레이션

연동 제약:
- OPM은 시세 루프를 직접 소유하지 않는다.
- TSE가 `DEGRADED`로 신규 BUY를 차단해도, OPM은 기존 포지션의 SELL/정합/복구 처리를 계속 수행해야 한다.
- SELL 가격 계산에 사용하는 `current_price`는 최신 시세여야 하며, 허용 지연(`max_quote_staleness_ms`) 초과 시 주문을 거부한다.

권장 파라미터(v0.1.0):
- `max_quote_staleness_ms = 3000`

## 6.1 주문 생성 및 제출

```python
def place_buy_order(command: PlaceBuyOrderCommand) -> OrderAggregate:
    guard_recovery_completed(command.trading_date)
    assert_position_state_allows_buy(command.trading_date, command.symbol)

    qty = calc_buy_quantity(command.budget, command.current_price)
    client_order_id = build_client_order_id(
        trading_date=command.trading_date,
        symbol=command.symbol,
        side="BUY",
    )

    existing = order_store.find_by_client_order_id(client_order_id)
    if existing is not None:
        return existing

    order = create_pending_buy_order(command, qty, client_order_id)
    publish_order_event(order, "PENDING_SUBMIT")

    try:
        order = on_submit_requested(order, now=clock.now())
        result = kia.submit_order(
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            price=order.requested_price,
            qty=order.requested_qty,
            order_type=order.order_type,
        )

        if result["status"] == "ACCEPTED":
            order = on_submit_accepted(order, broker_order_id=result["brokerOrderId"], now=clock.now())
        else:
            order = on_submit_rejected(order, reason_code=result.get("errorCode", "OPM_KIA_NON_RETRYABLE"), now=clock.now())

        publish_order_event(order, order.status)
        return order

    except KiaRequestTimeoutError:
        order = on_submit_timeout(order, now=clock.now())
        publish_order_event(order, "RECONCILING")
        reconcile_service.start_reconciliation(order, reason_code="OPM_ORDER_SUBMIT_TIMEOUT")
        return order
```

```python
def guard_fresh_quote(now: datetime, quote_as_of: datetime, max_staleness_ms: int = 3000) -> None:
    staleness_ms = int((now - quote_as_of).total_seconds() * 1000)
    if staleness_ms > max_staleness_ms:
        raise OpmValidationError(
            code="OPM_STALE_MARKET_PRICE",
            detail=f"stalenessMs={staleness_ms}",
        )
```

## 6.2 체결 반영(멱등 포함)

```python
def apply_execution_result(
    order: OrderAggregate,
    fills: list[ExecutionFill],
    broker_remaining_qty: int,
    latest_market_price: Decimal,
) -> tuple[OrderAggregate, PositionModel]:
    position = position_store.get(order.trading_date, order.symbol)

    for fill in fills:
        if execution_ledger.exists(fill.execution_id):
            continue

        execution_ledger.add(fill.execution_id)
        order = apply_fill_to_order(order, fill)
        position = apply_fill_to_position(position, order.side, fill)

        publish_execution_event(order, fill)

    order = sync_order_remaining(order, broker_remaining_qty)
    order = derive_order_status(order)

    position.current_price = latest_market_price
    position = recalc_interim_pnl(position)
    position = maybe_update_position_state(position, order)

    publish_order_event(order, order.status)
    publish_position_snapshot(position)

    return order, position
```

## 7. 주문 정합(Reconciliation) 알고리즘

## 7.1 Reconcile Task 모델

```python
@dataclass(frozen=True)
class ReconcileTask:
    trading_date: date
    symbol: str
    order_aggregate_id: str
    broker_order_id: str | None
    client_order_id: str
    reason_code: str
    attempt: int
    next_run_at: datetime

@dataclass(frozen=True)
class ReconcileResult:
    order_aggregate_id: str
    resolved_status: OrderStatus
    applied_fill_count: int
    mismatch_detected: bool
    mismatch_reason: str | None
```

## 7.2 정합 처리 단계

```python
def run_reconcile_once(trading_date: date, symbol: str) -> None:
    task = reconcile_queue.pop_due(trading_date=trading_date, symbol=symbol)
    if task is None:
        return

    order = order_store.get(task.order_aggregate_id)
    if order.status not in {"RECONCILING", "SUBMITTED", "ACCEPTED", "PARTIALLY_FILLED"}:
        return

    execution_result = retry_fetch_execution(
        broker_order_id=task.broker_order_id,
        client_order_id=task.client_order_id,
    )

    new_fills = filter_new_fills(execution_result.fills, execution_ledger)
    order, position = execution_service.apply_execution_result(
        order=order,
        fills=new_fills,
        broker_remaining_qty=execution_result.remaining_qty,
        latest_market_price=market_price_provider.get(symbol),
    )

    mismatch = detect_mismatch(
        internal_remaining_qty=order.remaining_qty,
        broker_remaining_qty=execution_result.remaining_qty,
        internal_cum_qty=order.cum_executed_qty,
        broker_cum_qty=execution_result.cum_qty,
    )

    if mismatch is not None:
        broker_position = retry_fetch_position(symbol=symbol)
        order, position = apply_position_correction(order, position, broker_position)
        publish_order_event(order, "RECONCILING")

    if order.status == "RECONCILING":
        schedule_next_reconcile(task)
```

## 7.3 불일치 판정 함수

```python
def detect_mismatch(
    *,
    internal_remaining_qty: int,
    broker_remaining_qty: int,
    internal_cum_qty: int,
    broker_cum_qty: int,
) -> str | None:
    if internal_remaining_qty != broker_remaining_qty:
        return "OPM_RECON_MISMATCH_REMAINING_QTY"
    if internal_cum_qty != broker_cum_qty:
        return "OPM_RECON_MISMATCH_CUM_QTY"
    return None
```

## 8. 복구(Startup Recovery) 흐름

```python
def recover_on_startup(trading_date: date) -> None:
    begin_recovery_mode(trading_date)

    snapshots = prp.find_latest_snapshot_all_symbols(trading_date)
    restore_position_store_from_snapshots(snapshots)

    open_orders = order_store.find_open_orders(
        trading_date=trading_date,
        statuses=["SUBMITTED", "ACCEPTED", "PARTIALLY_FILLED", "RECONCILING"],
    )

    for order in open_orders:
        reconcile_service.start_reconciliation(order, reason_code="OPM_STARTUP_RECOVERY")

    reconcile_service.run_reconcile_batch(max_batch_size=1000)
    flush_prp_retry_queue()

    finish_recovery_mode(trading_date)
```

복구 가드:
- `recovery_mode=true` 동안 `place_buy_order`/`place_sell_order`는 `OpmRecoveryInProgressError` 발생
- 복구 종료 이벤트를 PRP 감사 로그로 저장

## 9. 예외 처리 계약 (Exception Handling Contracts)

## 9.1 예외 계층

```python
class OpmError(Exception):
    code: str
    retryable: bool
    severity: Literal["INFO", "WARN", "ERROR"]

class OpmValidationError(OpmError): ...
class OpmStateError(OpmError): ...
class OpmKiaError(OpmError): ...
class OpmPrpError(OpmError): ...
class OpmReconciliationError(OpmError): ...
```

## 9.2 표준 코드 매핑

| 예외 클래스 | code | retryable | 처리 원칙 |
|---|---|---:|---|
| `OpmInvalidMarketPriceError` | `OPM_INVALID_MARKET_PRICE` | false | 요청 거부, 주문 생성 중단 |
| `OpmInvalidSellPriceError` | `OPM_INVALID_SELL_PRICE` | false | 매도 주문 거부, WARN 이벤트 저장 |
| `OpmInvalidTickSizeError` | `OPM_INVALID_TICK_SIZE` | false | KIA quote 검증 실패로 처리 |
| `OpmInvalidStateTransitionError` | `OPM_INVALID_STATE_TRANSITION` | false | 상태 갱신 중단, ERROR 로깅 |
| `OpmValidationError(code=OPM_STALE_MARKET_PRICE)` | `OPM_STALE_MARKET_PRICE` | false | stale 시세 기반 주문 거부 |
| `KiaRetryableWrappedError` | `OPM_KIA_RETRYABLE` | true | 조회성 호출 최대 3회 재시도 |
| `KiaNonRetryableWrappedError` | `OPM_KIA_NON_RETRYABLE` | false | 주문 거부 이벤트 저장 후 종료 |
| `OpmOrderSubmitTimeoutError` | `OPM_ORDER_SUBMIT_TIMEOUT` | true | 재주문 금지, `RECONCILING` 전환 |
| `PrpWriteTemporaryError` | `OPM_PRP_WRITE_FAILED` | true | 메모리 큐 적재 후 재플러시 |
| `ReconcileFailedError` | `OPM_RECONCILIATION_FAILED` | false | 수동 확인 필요 플래그 발행 |
| `OpmRecoveryInProgressError` | `OPM_RECOVERY_IN_PROGRESS` | true | 복구 완료 전 신규 주문 차단 |

## 9.3 서비스 경계별 예외 계약

```python
@dataclass(frozen=True)
class OpmErrorContract:
    code: str
    message: str
    retryable: bool
    severity: Literal["INFO", "WARN", "ERROR"]
    context: dict[str, str]


def to_error_contract(exc: Exception, context: dict[str, str]) -> OpmErrorContract: ...
```

계약 원칙:
- 내부 예외는 서비스 경계에서 `OpmErrorContract`로 변환
- UI/UAG 노출 메시지는 한국어 고정, 내부 로그는 구조화 JSON
- `retryable=true`라도 주문 제출(`submit_order`)은 즉시 재시도 금지

## 10. PRP 저장 실패 임시 큐/재시도

```python
def publish_with_retry(action: str, payload: dict) -> None:
    backoffs_ms = [200, 400, 800]
    for delay in backoffs_ms:
        try:
            prp_dispatch(action, payload)
            return
        except PrpWriteTemporaryError:
            sleep_ms(delay)
    failed_queue.push(action=action, payload=payload)


def flush_prp_retry_queue(max_items: int = 500) -> int:
    flushed = 0
    while flushed < max_items:
        item = failed_queue.pop()
        if item is None:
            break
        publish_with_retry(item.action, item.payload)
        flushed += 1
    return flushed
```

## 11. 테스트 포인트 (구현 검증 기준)

- 상태 전이 검증: 허용/비허용 전이 케이스 전수 테스트
- 틱 규칙 검증: 경계값(999, 1000, 4999, 5000, 9999, 10000, 49999, 50000, 99999, 100000)
- 매도 2틱 계산: 정상/음수/0원 산출 예외 테스트
- 멱등성 검증: 동일 `client_order_id`, 동일 `execution_id` 재처리 차단
- 정합 알고리즘: timeout -> reconciling -> filled/rejected 분기 테스트
- 불일치 보정: `remainingQty`/`cumQty` 불일치 시 `fetchPosition` 보정 확인
- PRP 실패 큐: 저장 실패 후 큐 적재/재플러시 성공 테스트
- 복구 가드: 복구 중 신규 주문 차단 및 종료 후 허용 테스트
- TSE `DEGRADED` 상태에서도 SELL/정합 워커가 중단되지 않는지 검증
- stale 시세(`quote_as_of` 지연 초과) 기반 SELL 요청 시 `OPM_STALE_MARKET_PRICE` 거부 검증

## 12. LLD 추적성 매트릭스

| LLD-OPM 섹션 | 구현 반영 섹션 |
|---|---|
| 3장 주문 수명주기 상태머신 | 4장 상태 전이 핸들러 |
| 4장 가격/틱 규칙 | 5장 틱 사이즈 유틸 |
| 6장 OPM-KIA/PRP 계약 | 3.4, 6장, 10장 |
| 7장 멱등성/정합/복구 | 6.2, 7장, 8장 |
| 9장 핵심 의사코드 | 6장, 7장 구체 함수 |
| 10장 오류/재시도 정책 | 9장 예외 계약, 10장 재시도 |

---
본 문서는 LLD-OPM v0.1.0을 코드 구현 가능한 메서드/핸들러/계약 수준으로 상세화한 ILD이다.
