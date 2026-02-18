# ILD-TSE v0.1.0

- 문서명: TSE 모듈 구현 상세 설계서 (ILD)
- 버전: v0.1.0
- 작성일: 2026-02-17
- 기반 문서:
  - `docs/lld/LLD-TSE-v0.1.0.md`
  - `docs/lld/LLD-OPM-v0.1.0.md`
  - `docs/lld/LLD-PRP-v0.1.0.md`
  - `docs/hld/HLD-v0.1.0.md`
  - `docs/srs/SRS-v0.1.0.md`
- 모듈: `TSE` (Trading Strategy Engine)
- 언어/런타임 가정: Python 3.12+, `Decimal` 기반 계산, 단일 프로세스 이벤트 루프 + 심볼 스캔 스케줄러

## 1. 구현 범위

LLD-TSE의 전략 상태머신/시간 경계/단일 매수 제약을 실제 구현 단위로 세분화한다.

- 종목 단위 매수 전 상태머신(`WAIT_REFERENCE`, `TRACKING`, `BUY_CANDIDATE`, `BUY_TRIGGERED`, `BUY_BLOCKED`) 구현
- 포트폴리오 단위 전역 게이트(`globalBuyGate`) 및 단일 전액 매수 제약 구현
- 매수 후 수익 보호 상태(`PROFIT_UNLOCKED`/`PROFIT_LOCKED`) 및 매도 트리거 구현
- 장중 시세 지속 조회 루프(`RUNNING`/`DEGRADED`/`STOPPED`) 구현
- 심볼 스캔 스케줄러(우선순위: 시각→시퀀스→목록순) 구현
- OPM 명령 발행/PRP 전략 이벤트 발행 오케스트레이션 구현
- 임계치 계산 규칙을 순수 함수로 분리하여 단위 테스트 가능 구조 확정

비범위:
- 주문 수량 산정/주문 체결 관리(OPM)
- 브로커 API 호출 및 인증(KIA)
- 리포트 집계/조회(PRP)

## 1.1 코드 기준 책임 경계 반영(2026-02-18)

코드 기준으로 TSE의 시세 입력 경로를 아래처럼 고정한다.

- 전략 시세 입력은 `KIA.fetch_quotes_batch` 결과를 `QuoteEvent`로 변환하여 `TSE.on_quote`에 공급한다.
- `OPM.poll_realtime_execution_event` 경로의 `realtime_receive`는 체결/잔고(type `00`, `04`) 처리 전용이며, TSE 호가 입력으로 사용하지 않는다.
- 호가 루프와 체결 루프는 런타임에서 독립 실행하고, 한쪽 장애가 다른 쪽 루프를 중단시키지 않도록 한다.

## 2. 디렉터리/모듈 구조 제안

```text
src/
  tse/
    __init__.py
    bootstrap.py

    constants.py                 # 임계치/시간/EPS 상수

    domain/
      __init__.py
      enums.py                   # SymbolState, PortfolioState, ProfitState, GateState
      models.py                  # SymbolContext, PortfolioContext, DailyContext
      transitions.py             # 결정적 상태 전이 함수
      rules.py                   # drop/rebound/profit/preservation 순수 함수
      scheduler.py               # scan queue + tie-breaker
      validators.py              # tradingDate/time/price 유효성 검사

    dto/
      __init__.py
      input_dto.py               # QuoteEvent, PositionUpdateEvent
      command_dto.py             # PlaceBuyOrderCommand, PlaceSellOrderCommand
      strategy_event_dto.py      # StrategyEvent payload

    service/
      __init__.py
      tse_service.py             # on_quote, on_position_update, on_day_changed
            quote_polling_service.py   # run_poll_loop, stop_poll_loop
      buy_signal_service.py      # try_emit_buy_signal (원자 게이트 획득)
      sell_signal_service.py     # try_emit_sell_signal
      scheduler_service.py       # ingest_quote, flush_due_candidates

    gateway/
      __init__.py
            kia_gateway.py             # fetch_quotes_batch
      opm_gateway.py             # place_buy_order/place_sell_order
      prp_gateway.py             # save_strategy_event

    infra/
      __init__.py
      clock.py
      sequence.py                # quote 수신 단조 sequence
      lock_manager.py            # tradingDate 단위 gate 락

    errors/
      __init__.py
      exceptions.py              # TSE 예외 계층

tests/
  tse/
    test_rules_thresholds.py
    test_symbol_state_transitions.py
    test_global_buy_gate.py
    test_scheduler_priority.py
    test_profit_lock_and_sell.py
    test_trading_day_boundary.py
```

## 3. 타입 및 클래스/함수 시그니처

### 3.1 상수

```python
from decimal import Decimal
from datetime import time

REFERENCE_CAPTURE_TIME = time(9, 3, 0)
DROP_THRESHOLD_PCT = Decimal("1.0")
REBOUND_THRESHOLD_PCT = Decimal("0.2")
MIN_PROFIT_LOCK_PCT = Decimal("1.0")
PROFIT_PRESERVATION_SELL_PCT = Decimal("80.0")
MAX_WATCH_SYMBOLS = 20
EPS = Decimal("0.0001")
QUOTE_POLL_INTERVAL_MS = 1000
QUOTE_POLL_TIMEOUT_MS = 700
QUOTE_CONSECUTIVE_ERROR_THRESHOLD = 3
QUOTE_RECOVERY_SUCCESS_THRESHOLD = 2
```

### 3.2 도메인 타입

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

SymbolState = Literal[
    "WAIT_REFERENCE",
    "TRACKING",
    "BUY_CANDIDATE",
    "BUY_TRIGGERED",
    "BUY_BLOCKED",
]

PortfolioState = Literal[
    "NO_POSITION",
    "BUY_REQUESTED",
    "POSITION_OPEN",
    "SELL_REQUESTED",
    "POSITION_CLOSED",
]

ProfitState = Literal["PROFIT_UNLOCKED", "PROFIT_LOCKED"]
GateState = Literal["OPEN", "CLOSED"]
LoopState = Literal["RUNNING", "DEGRADED", "STOPPED"]

@dataclass
class SymbolContext:
    symbol: str
    watch_rank: int
    state: SymbolState = "WAIT_REFERENCE"
    base_price: Decimal | None = None
    local_low: Decimal | None = None
    last_quote_at: datetime | None = None
    last_sequence: int = 0

@dataclass
class PortfolioContext:
    state: PortfolioState = "NO_POSITION"
    gate_state: GateState = "OPEN"
    active_symbol: str | None = None
    profit_state: ProfitState = "PROFIT_UNLOCKED"
    min_profit_locked: bool = False
    sell_signaled: bool = False

@dataclass
class DailyContext:
    trading_date: date
    symbols: dict[str, SymbolContext]
    portfolio: PortfolioContext = field(default_factory=PortfolioContext)
    reference_capture_done_count: int = 0
    loop_state: LoopState = "STOPPED"
    quote_consecutive_errors: int = 0
    quote_consecutive_success: int = 0
    buy_entry_blocked_by_degraded: bool = False
```

### 3.3 입력 DTO

```python
@dataclass(frozen=True)
class QuoteEvent:
    trading_date: date
    occurred_at: datetime
    poll_cycle_id: str
    symbol: str
    current_price: Decimal
    sequence: int

@dataclass(frozen=True)
class PositionUpdateEvent:
    trading_date: date
    symbol: str
    position_state: Literal["BUY_REQUESTED", "LONG_OPEN", "SELL_REQUESTED", "CLOSED"]
    avg_buy_price: Decimal
    current_price: Decimal
    current_profit_rate: Decimal
    max_profit_rate: Decimal
    min_profit_locked: bool
    updated_at: datetime
```

### 3.4 서비스 인터페이스

```python
from typing import Protocol

class TseService(Protocol):
    def start_poll_loop(self, trading_date: date) -> None: ...
    def stop_poll_loop(self, trading_date: date, reason: str) -> None: ...
    def on_quote(self, event: QuoteEvent) -> None: ...
    def on_position_update(self, event: PositionUpdateEvent) -> None: ...
    def on_day_changed(self, trading_date: date) -> None: ...

class BuySignalService(Protocol):
    def try_emit_buy_signal(self, ctx: DailyContext, symbol_ctx: SymbolContext, quote: QuoteEvent) -> bool: ...

class SellSignalService(Protocol):
    def try_emit_sell_signal(self, ctx: DailyContext, position: PositionUpdateEvent) -> bool: ...

class SymbolScanScheduler(Protocol):
    def enqueue_candidate(self, quote: QuoteEvent, watch_rank: int) -> None: ...
    def flush_due_candidates(self, trading_date: date) -> list[QuoteEvent]: ...
    def clear_for_new_day(self, trading_date: date) -> None: ...


class KiaQuoteGateway(Protocol):
    def fetch_quotes_batch(self, *, symbols: list[str], timeout_ms: int, poll_cycle_id: str) -> dict: ...
```

### 3.5 Rule 함수(순수 함수, 단위 테스트 대상)

```python
from decimal import Decimal


def is_positive_price(price: Decimal) -> bool: ...

def calc_drop_rate(base_price: Decimal, current_price: Decimal) -> Decimal: ...

def calc_rebound_rate(local_low: Decimal, current_price: Decimal) -> Decimal: ...

def calc_profit_rate(avg_buy_price: Decimal, current_price: Decimal) -> Decimal: ...

def calc_profit_preservation_rate(current_profit_rate: Decimal, max_profit_rate: Decimal) -> Decimal: ...

def ge_with_eps(left: Decimal, right: Decimal, eps: Decimal = EPS) -> bool: ...

def le_with_eps(left: Decimal, right: Decimal, eps: Decimal = EPS) -> bool: ...


def should_enter_buy_candidate(drop_rate: Decimal) -> bool: ...

def should_update_local_low(current_price: Decimal, local_low: Decimal) -> bool: ...

def should_trigger_rebound_buy(rebound_rate: Decimal) -> bool: ...

def should_lock_min_profit(current_profit_rate: Decimal) -> bool: ...

def should_emit_sell_signal(
    *,
    min_profit_locked: bool,
    current_profit_rate: Decimal,
    max_profit_rate: Decimal,
) -> bool: ...
```

## 4. 구현 절차 (Procedure)

### 4.1 부트스트랩 및 일일 컨텍스트 초기화

1) 감시 종목 목록(1~20) 로드 및 `watch_rank` 할당
2) `DailyContext` 생성 시 모든 종목 `WAIT_REFERENCE`, 포트폴리오 `NO_POSITION`, 게이트 `OPEN`
3) 거래일 키(`trading_date`)를 컨텍스트 키로 사용
4) 거래일 변경 감지 시 이전 일자 컨텍스트 폐기 후 신규 생성

### 4.2 시세 이벤트 처리 파이프라인

1) 입력 검증: `trading_date` 일치, `current_price > 0`, 감시 목록 포함 여부
2) 09:03 이전이면 기준가/상태 전이 평가 없이 종료
3) 종목 `base_price` 미확정이면 현재가로 1회 확정하고 `TRACKING` 전이
4) `buy_entry_blocked_by_degraded=True`이면 신규 BUY 진입 판단은 건너뛰고 종료
5) `dropRate` 계산 후 1.0% 이상이면 `BUY_CANDIDATE` 진입 또는 `local_low` 갱신
6) `BUY_CANDIDATE` 상태에서 `reboundRate` 계산 후 0.2% 이상이면 스케줄러 큐 등록
7) 스케줄러가 선택한 1건에 대해 게이트 원자 획득 시 `PlaceBuyOrderCommand` 발행
8) 발행 성공 시 `BUY_TRIGGERED` 및 포트폴리오 `BUY_REQUESTED`, 게이트 `CLOSED`
9) 미선정/게이트 획득 실패 종목은 `BUY_BLOCKED`

### 4.3 포지션 업데이트 처리 파이프라인

1) `active_symbol`과 이벤트 심볼 불일치 시 무시
2) 포트폴리오 상태를 OPM 상태와 동기화 (`BUY_REQUESTED`/`LONG_OPEN`/`SELL_REQUESTED`/`CLOSED`)
3) `LONG_OPEN`에서 `current_profit_rate >= 1.0` 최초 도달 시 `MIN_PROFIT_LOCKED` 이벤트 발행
4) 락 이후 `profitPreservationRate <= 80.0`이면 1회 `PlaceSellOrderCommand` 발행
5) 매도 신호 발행 후 `sell_signaled=True`로 중복 방지

### 4.4 매수 실패/거래일 경계 처리

- OPM이 매수 거부/취소/만료를 알려오면 포트폴리오를 `NO_POSITION`으로 롤백하고 게이트 재개방
- 거래일 경계에서 모든 종목 상태, `active_symbol`, `min_profit_locked`, `sell_signaled` 초기화
- 지연 도착 이벤트(`event.trading_date != current_trading_date`)는 폐기

### 4.5 시세 지속 조회 루프 처리

1) `start_poll_loop` 호출 시 `loop_state=RUNNING`, 오류/성공 연속 카운터 초기화
2) 루프 1사이클마다 `KIA.fetch_quotes_batch(symbols, timeoutMs, pollCycleId)` 호출
3) 성공 종목 `quotes[]`를 `sequence` 순서로 `on_quote`에 전달
4) 사이클 실패 시 `quote_consecutive_errors += 1`, 성공 시 0으로 리셋
5) 연속 실패가 임계치 이상이면 `loop_state=DEGRADED`, `buy_entry_blocked_by_degraded=True`
6) `DEGRADED` 상태에서 성공 사이클 연속 임계치 충족 시 `loop_state=RUNNING` 복귀
7) `stop_poll_loop` 또는 거래일 종료 시 `loop_state=STOPPED`

루프 연동 경계 규칙:
- `QuotePollingLoop`는 `fetch_quotes_batch`만 호출하며 WebSocket `realtime_receive`를 호출하지 않는다.
- 체결/잔고 실시간 업데이트는 OPM 경로(`poll_and_apply_realtime_execution_event`)에서 처리된 결과를 `on_position_update`로 전달받아 반영한다.
- `DEGRADED`는 호가 루프 품질 상태만 의미하며, 보유 포지션의 매도 판단 입력은 계속 처리한다.

## 5. 결정적 상태 전이 명세

## 5.1 종목 상태머신 전이표

| 현재 상태 | 입력 조건 | 다음 상태 | 부수효과 |
|---|---|---|---|
| WAIT_REFERENCE | `time >= 09:03` & `base_price is None` | TRACKING | `base_price=current_price` |
| TRACKING | `dropRate >= 1.0` | BUY_CANDIDATE | `local_low=current_price`, `BUY_CANDIDATE_ENTERED` |
| BUY_CANDIDATE | `current_price < local_low` | BUY_CANDIDATE | `local_low=current_price`, `LOCAL_LOW_UPDATED` |
| BUY_CANDIDATE | `reboundRate >= 0.2` & 스케줄러 미선정 | BUY_CANDIDATE | 큐 대기 유지 |
| BUY_CANDIDATE | `reboundRate >= 0.2` & 스케줄러 선정 & 게이트 OPEN | BUY_TRIGGERED | BUY 명령 발행, `BUY_SIGNAL` |
| BUY_CANDIDATE | `reboundRate >= 0.2` & 게이트 CLOSED | BUY_BLOCKED | `BUY_SIGNAL_BLOCKED` 감사 로그 |
| BUY_BLOCKED | 거래일 변경 | WAIT_REFERENCE | 일일 초기화 |

결정성 보장 규칙:
- 동일 입력(`trading_date`, `symbol`, `occurred_at`, `sequence`, `price`)에 대해 동일 결과 상태를 반환한다.
- 전이 함수는 외부 I/O를 수행하지 않고 `(next_state, actions[])`를 반환한다.
- 실행기는 `actions[]`를 순서대로 실행하며 실패 시 롤백 정책을 적용한다.

## 5.2 포트폴리오 상태머신 전이표

| 현재 상태 | 이벤트 | 다음 상태 | 부수효과 |
|---|---|---|---|
| NO_POSITION | BUY 승인 | BUY_REQUESTED | `active_symbol` 설정, 게이트 `CLOSED` |
| BUY_REQUESTED | BUY 체결(`LONG_OPEN`) | POSITION_OPEN | 없음 |
| BUY_REQUESTED | BUY 실패(거부/취소/만료) | NO_POSITION | 게이트 `OPEN`, 재탐색 허용 |
| POSITION_OPEN | SELL 승인 | SELL_REQUESTED | `sell_signaled=True` |
| SELL_REQUESTED | SELL 체결(`CLOSED`) | POSITION_CLOSED | 없음 |
| POSITION_CLOSED | 거래일 변경 | NO_POSITION | 일일 초기화 |

## 5.3 수익 보호 서브상태 전이표

| 현재 ProfitState | 조건 | 다음 ProfitState | 부수효과 |
|---|---|---|---|
| PROFIT_UNLOCKED | `current_profit_rate >= 1.0` | PROFIT_LOCKED | `min_profit_locked=True`, `MIN_PROFIT_LOCKED` |
| PROFIT_LOCKED | `preservation <= 80.0` & `sell_signaled=False` | PROFIT_LOCKED | SELL 명령 발행, `SELL_SIGNAL` |
| PROFIT_LOCKED | 그 외 | PROFIT_LOCKED | 없음 |

## 6. 심볼 스캔 스케줄러 로직

## 6.1 목적

동일 시점 다중 매수 트리거 상황에서 LLD 우선순위(시각→시퀀스→목록순)를 코드로 고정한다.

## 6.2 내부 자료구조

```python
from dataclasses import dataclass
from datetime import datetime
from heapq import heappush, heappop

@dataclass(frozen=True, order=True)
class CandidateKey:
    occurred_at: datetime
    sequence: int
    watch_rank: int

@dataclass(frozen=True)
class BuyCandidate:
    key: CandidateKey
    trading_date: date
    symbol: str
    current_price: Decimal
    rebound_rate: Decimal
```

- 최소 힙(`heapq`)으로 `CandidateKey` 오름차순 우선순위 보장
- 큐 원소는 거래일별 분리 저장
- `gate_state == CLOSED`이면 pop 없이 유지(재탐색 불필요 시 flush)

## 6.3 스케줄러 동작 절차

1) `BUY_CANDIDATE`에서 반등 충족 시 `enqueue_candidate`
2) 이벤트 루프 tick마다 `flush_due_candidates` 호출
3) 힙 pop으로 최고 우선순위 후보 1건 선택
4) 게이트 OPEN이면 즉시 BUY 승인 시도
5) 승인 성공 시 즉시 flush 종료(단일 매수)
6) 승인 실패/게이트 CLOSED면 해당 종목 `BUY_BLOCKED` 처리

## 6.4 스케줄러 의사코드

```text
function flush_due_candidates(ctx):
  if ctx.portfolio.gate_state == CLOSED:
    return

  while heap not empty:
    candidate = pop_min(heap)   # occurredAt, sequence, watchRank 순
    symbolCtx = ctx.symbols[candidate.symbol]

    if symbolCtx.state != BUY_CANDIDATE:
      continue

    acquired = tryAcquireGlobalBuyGate(ctx, candidate.symbol)
    if acquired:
      emitBuyCommand(candidate)
      symbolCtx.state = BUY_TRIGGERED
      return

    symbolCtx.state = BUY_BLOCKED
```

## 7. Rule 함수 상세(임계치/경계)

## 7.1 계산 함수 구현 규칙

```python
from decimal import Decimal, ROUND_HALF_UP

PCT_Q = Decimal("0.0001")


def _q4(value: Decimal) -> Decimal:
    return value.quantize(PCT_Q, rounding=ROUND_HALF_UP)


def calc_drop_rate(base_price: Decimal, current_price: Decimal) -> Decimal:
    if base_price <= 0:
        raise ValueError("base_price must be > 0")
    return _q4((base_price - current_price) / base_price * Decimal("100"))


def calc_rebound_rate(local_low: Decimal, current_price: Decimal) -> Decimal:
    if local_low <= 0:
        raise ValueError("local_low must be > 0")
    return _q4((current_price - local_low) / local_low * Decimal("100"))


def calc_profit_preservation_rate(current_profit_rate: Decimal, max_profit_rate: Decimal) -> Decimal:
    if max_profit_rate <= 0:
        raise ValueError("max_profit_rate must be > 0")
    return _q4(current_profit_rate / max_profit_rate * Decimal("100"))
```

## 7.2 임계치 판정 함수 구현 규칙

```python
def ge_with_eps(left: Decimal, right: Decimal, eps: Decimal = EPS) -> bool:
    return left >= (right - eps)


def le_with_eps(left: Decimal, right: Decimal, eps: Decimal = EPS) -> bool:
    return left <= (right + eps)


def should_enter_buy_candidate(drop_rate: Decimal) -> bool:
    return ge_with_eps(drop_rate, DROP_THRESHOLD_PCT)


def should_trigger_rebound_buy(rebound_rate: Decimal) -> bool:
    return ge_with_eps(rebound_rate, REBOUND_THRESHOLD_PCT)


def should_lock_min_profit(current_profit_rate: Decimal) -> bool:
    return ge_with_eps(current_profit_rate, MIN_PROFIT_LOCK_PCT)


def should_emit_sell_signal(*, min_profit_locked: bool, current_profit_rate: Decimal, max_profit_rate: Decimal) -> bool:
    if not min_profit_locked:
        return False
    if max_profit_rate <= 0:
        return False
    preservation = calc_profit_preservation_rate(current_profit_rate, max_profit_rate)
    return le_with_eps(preservation, PROFIT_PRESERVATION_SELL_PCT)
```

## 7.3 단위 테스트 케이스(필수)

| 테스트 ID | 함수 | 입력 | 기대 결과 |
|---|---|---|---|
| RT-001 | `should_enter_buy_candidate` | `drop=1.0000` | `True` |
| RT-002 | `should_enter_buy_candidate` | `drop=0.9999` | `True` (EPS 허용) |
| RT-003 | `should_trigger_rebound_buy` | `rebound=0.2000` | `True` |
| RT-004 | `should_trigger_rebound_buy` | `rebound=0.1998` | `False` |
| RT-005 | `should_lock_min_profit` | `profit=1.0000` | `True` |
| RT-006 | `should_emit_sell_signal` | `locked=True, current=0.80, max=1.00` | `True` |
| RT-007 | `should_emit_sell_signal` | `locked=True, current=0.81, max=1.00` | `False` |
| RT-008 | `calc_profit_preservation_rate` | `max<=0` | `ValueError` |

## 8. 이벤트/명령 매핑 구현

## 8.1 TSE -> OPM 명령 생성기

```python
def make_buy_command(quote: QuoteEvent, trading_date: date) -> PlaceBuyOrderCommand: ...

def make_sell_command(position: PositionUpdateEvent) -> PlaceSellOrderCommand: ...
```

매핑 규칙:
- BUY `reasonCode = "TSE_REBOUND_BUY_SIGNAL"`
- SELL `reasonCode = "TSE_PROFIT_PRESERVATION_BREAK"`
- `commandId`는 `tradingDate-symbol-side-seq` 포맷으로 결정적 생성

## 8.2 TSE -> PRP 전략 이벤트 매핑

발행 이벤트:
- `BUY_CANDIDATE_ENTERED`
- `LOCAL_LOW_UPDATED`
- `BUY_SIGNAL`
- `MIN_PROFIT_LOCKED`
- `SELL_SIGNAL`

payload 필수 필드:
- `tradingDate`, `symbol`, `occurredAt`, `strategyState`, `metrics`
- `metrics`는 이벤트별 최소 필드(`dropRate`, `reboundRate`, `profitPreservationRate` 등) 포함

실패 처리:
- PRP 저장 실패 시 TSE 상태 전이는 유지
- 실패 이벤트는 경고 로그 + 재시도 큐(최대 3회)로 이관

## 9. 예외/검증/가드

- 감시 종목 수 검증: 시작 시 `1 <= len(symbols) <= 20` 아니면 부팅 실패
- 가격 검증: `current_price <= 0`이면 이벤트 폐기 + 검증 오류 로그
- 거래일 검증: 컨텍스트 거래일과 다르면 즉시 폐기
- 중복 SELL 가드: `sell_signaled=True`면 SELL 재발행 금지
- 중복 BUY 가드: `portfolio.state != NO_POSITION` 또는 게이트 `CLOSED`면 BUY 금지

## 10. 테스트 전략

## 10.1 상태 전이 단위 테스트

- 심볼 상태 전이: `WAIT_REFERENCE -> TRACKING -> BUY_CANDIDATE -> BUY_TRIGGERED/BLOCKED`
- 포트폴리오 전이: `NO_POSITION -> BUY_REQUESTED -> POSITION_OPEN -> SELL_REQUESTED -> POSITION_CLOSED`
- 수익 락 전이: `PROFIT_UNLOCKED -> PROFIT_LOCKED`

## 10.2 스케줄러 우선순위 테스트

- 동일 시각/서로 다른 sequence: 낮은 sequence 우선
- 동일 시각/동일 sequence: 낮은 watch_rank 우선
- 게이트 닫힘 상태: flush 시 BUY 0건 보장

## 10.3 통합 테스트(서비스 레벨)

- 시나리오 A: 1개 종목 정상 매수→수익락→매도
- 시나리오 B: 다중 종목 동시 반등, 최초 1건만 BUY
- 시나리오 C: BUY 실패 후 게이트 재개방, 후속 종목 BUY 허용
- 시나리오 D: 거래일 변경 시 상태 완전 초기화
- 시나리오 E: 시세 루프 연속 실패 3회 시 `DEGRADED` 전환 + 신규 BUY 차단
- 시나리오 F: 정상 사이클 2회 연속 시 `RUNNING` 자동 복귀 + BUY 재허용

## 11. 구현 체크리스트

- [ ] `rules.py` 순수 함수 구현 및 테스트 작성
- [ ] `transitions.py` 결정적 전이 함수 구현
- [ ] `scheduler.py` 힙 기반 우선순위 큐 구현
- [ ] `tse_service.py` on_quote/on_position_update 파이프라인 구현
- [ ] OPM/PRP 게이트웨이 연동 포인트 구현
- [ ] 거래일 경계 초기화 및 지연 이벤트 폐기 구현
- [ ] 단위/통합 테스트 통과

---
본 문서는 LLD-TSE를 클래스/함수/전이표/스케줄러/테스트 단위까지 구현 가능한 수준으로 구체화한 ILD이다.
