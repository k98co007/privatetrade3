# ILD-PRP v0.1.0

- 문서명: PRP 모듈 구현 상세 설계서 (ILD)
- 버전: v0.1.0
- 작성일: 2026-02-17
- 기반 문서:
  - `docs/lld/LLD-PRP-v0.1.0.md`
  - `docs/hld/HLD-v0.1.0.md` (4.6, 5, 6.2)
  - `docs/srs/SRS-v0.1.0.md` (FR-016, FR-017, NFR-003, NFR-004, NFR-005)
- 모듈: `PRP` (Persistence & Reporting)
- 언어/런타임 가정: Python 3.12+, SQLite3, 표준 라이브러리 중심

## 1. 구현 범위 및 비범위

### 1.1 범위 (LLD 1, 4, 5, 6)
- 전략/주문/체결 이벤트 영속화
- 포지션 스냅샷 저장/최신 스냅샷 조회
- 일자별 거래상세(`trade_details`) 생성 및 일일 리포트(`daily_reports`) 집계
- 재시작 복구 지원 API (`findLatestSnapshot`, `existsExecution` 등)
- UAG 조회용 응답 DTO 반환

### 1.2 비범위 (LLD 1)
- 전략 신호 계산 로직(TSE 책임)
- 주문 실행/체결 외부 API 연동(KIA/OPM 책임)

## 2. 디렉터리/모듈 레이아웃 제안

LLD의 DTO/저장소/복구 책임을 Python 패키지로 분해한다.

```text
src/
  prp/
    __init__.py
    bootstrap.py                 # DB 초기화, 스키마 마이그레이션 엔트리

    domain/
      __init__.py
      enums.py                   # EventType, Side, OrderStatus 등
      models.py                  # 내부 도메인 모델(dataclass)
      formulas.py                # 세금/수수료/PnL 계산 함수
      rounding.py                # Decimal quantize 규칙

    dto/
      __init__.py
      event_dto.py               # StrategyEvent, OrderEvent, ExecutionEvent, PositionSnapshot
      report_dto.py              # DailyReportResponse, TradeDetailResponse
      query_dto.py               # GetDailyReportQuery, GetTradeDetailsQuery
      error_dto.py               # 공통 오류 응답 DTO

    infra/
      __init__.py
      db/
        __init__.py
        connection.py            # sqlite connection factory, pragma 설정
        schema.sql               # DDL 원문
        migration.py             # schema_version, 최초/증분 마이그레이션
      repository/
        __init__.py
        base.py                  # Repository 공통 인터페이스
        event_repository.py
        snapshot_repository.py
        report_repository.py
      serializer/
        __init__.py
        json_codec.py            # payload_json 직렬화/역직렬화

    service/
      __init__.py
      persistence_service.py     # save* 계열 orchestration
      report_service.py          # generateDailyReport, getTradeDetails
      recovery_service.py        # recoverOnStartup 지원 메서드

    errors/
      __init__.py
      exceptions.py              # PRP 예외 계층
      contracts.py               # code/retryable 매핑

    logging/
      __init__.py
      audit_logger.py            # recovery completed, partial failure 등

tests/
  prp/
    test_formulas.py
    test_event_persistence.py
    test_report_generation.py
    test_recovery_flow.py
```

## 3. 타입/시그니처 설계 (Python)

### 3.1 공통 타입

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol

KST_ISO_TZ = "Asia/Seoul"
```

### 3.2 DTO/모델 시그니처 (LLD 2)

```python
@dataclass(frozen=True)
class StrategyEventDTO:
    event_id: str
    occurred_at: datetime
    trading_date: date
    symbol: str
    event_type: str
    base_price: Decimal | None
    local_low: Decimal | None
    current_price: Decimal | None
    payload: dict[str, Any] | None

@dataclass(frozen=True)
class OrderEventDTO:
    event_id: str
    order_id: str
    occurred_at: datetime
    trading_date: date
    symbol: str
    side: str
    order_type: str
    order_price: Decimal
    quantity: int
    status: str
    client_order_key: str
    reason_code: str | None
    reason_message: str | None

@dataclass(frozen=True)
class ExecutionEventDTO:
    event_id: str
    execution_id: str
    order_id: str
    occurred_at: datetime
    trading_date: date
    symbol: str
    side: str
    execution_price: Decimal
    execution_qty: int
    cum_qty: int
    remaining_qty: int

@dataclass(frozen=True)
class PositionSnapshotDTO:
    snapshot_id: str
    saved_at: datetime
    trading_date: date
    symbol: str
    avg_buy_price: Decimal
    quantity: int
    current_profit_rate: Decimal
    max_profit_rate: Decimal
    min_profit_locked: bool
    last_order_id: str | None
    state_version: int

@dataclass(frozen=True)
class TradeDetailDTO:
    id: str
    trading_date: date
    symbol: str
    buy_executed_at: datetime
    sell_executed_at: datetime
    quantity: int
    buy_price: Decimal
    sell_price: Decimal
    buy_amount: Decimal
    sell_amount: Decimal
    sell_tax: Decimal
    sell_fee: Decimal
    net_pnl: Decimal
    return_rate: Decimal

@dataclass(frozen=True)
class DailyReportDTO:
    trading_date: date
    total_buy_amount: Decimal
    total_sell_amount: Decimal
    total_sell_tax: Decimal
    total_sell_fee: Decimal
    total_net_pnl: Decimal
    total_return_rate: Decimal
    generated_at: datetime
```

### 3.3 서비스 인터페이스 시그니처 (LLD 4, 6)

```python
class PersistenceService(Protocol):
    def save_strategy_event(self, dto: StrategyEventDTO) -> None: ...
    def save_order_event(self, dto: OrderEventDTO) -> None: ...
    def save_execution_event(self, dto: ExecutionEventDTO) -> bool: ...
    def save_position_snapshot(self, dto: PositionSnapshotDTO) -> None: ...

class ReportService(Protocol):
    def generate_daily_report(self, trading_date: date) -> DailyReportDTO: ...
    def get_trade_details(self, trading_date: date, symbol: str | None = None) -> list[TradeDetailDTO]: ...

class RecoveryService(Protocol):
    def find_latest_snapshot(self, trading_date: date) -> PositionSnapshotDTO | None: ...
    def exists_execution(self, execution_id: str) -> bool: ...
    def write_recovery_log(self, trading_date: date, status: str) -> None: ...
```

## 4. SQL 스키마 DDL (LLD 3.2 구현본)

아래 DDL은 `src/prp/infra/db/schema.sql`에 그대로 반영한다.

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_events (
  event_id TEXT PRIMARY KEY,
  trading_date TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  symbol TEXT NOT NULL,
  event_type TEXT NOT NULL,
  base_price NUMERIC NULL,
  local_low NUMERIC NULL,
  current_price NUMERIC NULL,
  payload_json TEXT NULL
);
CREATE INDEX IF NOT EXISTS idx_strategy_events_date_symbol
ON strategy_events(trading_date, symbol, occurred_at);

CREATE TABLE IF NOT EXISTS order_events (
  event_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  trading_date TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  order_type TEXT NOT NULL,
  order_price NUMERIC NOT NULL,
  quantity INTEGER NOT NULL,
  status TEXT NOT NULL,
  client_order_key TEXT NOT NULL,
  reason_code TEXT NULL,
  reason_message TEXT NULL,
  UNIQUE(order_id, status, occurred_at)
);

CREATE TABLE IF NOT EXISTS execution_events (
  event_id TEXT PRIMARY KEY,
  execution_id TEXT NOT NULL UNIQUE,
  order_id TEXT NOT NULL,
  trading_date TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  execution_price NUMERIC NOT NULL,
  execution_qty INTEGER NOT NULL,
  cum_qty INTEGER NOT NULL,
  remaining_qty INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS position_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  saved_at TEXT NOT NULL,
  trading_date TEXT NOT NULL,
  symbol TEXT NOT NULL,
  avg_buy_price NUMERIC NOT NULL,
  quantity INTEGER NOT NULL,
  current_profit_rate NUMERIC NOT NULL,
  max_profit_rate NUMERIC NOT NULL,
  min_profit_locked INTEGER NOT NULL,
  last_order_id TEXT NULL,
  state_version INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_position_snapshots_date_savedat
ON position_snapshots(trading_date, saved_at DESC);

CREATE TABLE IF NOT EXISTS daily_reports (
  trading_date TEXT PRIMARY KEY,
  total_buy_amount NUMERIC NOT NULL,
  total_sell_amount NUMERIC NOT NULL,
  total_sell_tax NUMERIC NOT NULL,
  total_sell_fee NUMERIC NOT NULL,
  total_net_pnl NUMERIC NOT NULL,
  total_return_rate NUMERIC NOT NULL,
  generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trade_details (
  id TEXT PRIMARY KEY,
  trading_date TEXT NOT NULL,
  symbol TEXT NOT NULL,
  buy_executed_at TEXT NOT NULL,
  sell_executed_at TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  buy_price NUMERIC NOT NULL,
  sell_price NUMERIC NOT NULL,
  buy_amount NUMERIC NOT NULL,
  sell_amount NUMERIC NOT NULL,
  sell_tax NUMERIC NOT NULL,
  sell_fee NUMERIC NOT NULL,
  net_pnl NUMERIC NOT NULL,
  return_rate NUMERIC NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trade_details_date_symbol
ON trade_details(trading_date, symbol);
```

## 5. Repository 인터페이스/구현 규약

### 5.1 인터페이스

```python
from typing import Protocol
from datetime import date

class EventRepository(Protocol):
    def insert_strategy_event(self, dto: StrategyEventDTO) -> None: ...
    def insert_order_event(self, dto: OrderEventDTO) -> None: ...
    def insert_execution_event(self, dto: ExecutionEventDTO) -> bool: ...

class SnapshotRepository(Protocol):
    def insert_position_snapshot(self, dto: PositionSnapshotDTO) -> None: ...
    def select_latest_snapshot(self, trading_date: date) -> PositionSnapshotDTO | None: ...

class ReportRepository(Protocol):
    def select_execution_pairs(self, trading_date: date) -> list[tuple[ExecutionEventDTO, ExecutionEventDTO]]: ...
    def upsert_trade_details(self, details: list[TradeDetailDTO]) -> None: ...
    def upsert_daily_report(self, report: DailyReportDTO) -> None: ...
    def select_trade_details(self, trading_date: date, symbol: str | None) -> list[TradeDetailDTO]: ...

class RecoveryRepository(Protocol):
    def exists_execution(self, execution_id: str) -> bool: ...
```

### 5.2 구현 규약
- 트랜잭션 경계: 단일 유스케이스 단위(`with connection:`)
- `insert_execution_event`는 `execution_id` 충돌 시 `False` 반환(오류 아님)
- SQLite Row -> DTO 변환 시 Decimal은 `Decimal(str(value))`로 변환
- 날짜/시간은 DB에 ISO-8601 문자열(TEXT) 저장

## 6. 직렬화/역직렬화 포맷

### 6.1 DB 저장 포맷
- `trading_date`: `YYYY-MM-DD` 문자열
- `occurred_at`, `saved_at`, `generated_at`: `YYYY-MM-DDTHH:MM:SS+09:00`
- `payload_json`: UTF-8 JSON 문자열 (`json.dumps(..., ensure_ascii=False, separators=(',', ':'))`)
- `min_profit_locked`: SQLite INTEGER (`0/1`) ↔ Python `bool`

### 6.2 외부 응답(JSON) 포맷
- Decimal은 문자열이 아닌 숫자 JSON으로 직렬화하되, 소수 자리수는 반올림 후 출력
- 금액 필드: 소수점 2자리
- 수익률 필드: 소수점 4자리

예시:
```json
{
  "totalNetPnl": 11475.51,
  "totalReturnRate": 1.1608
}
```

## 7. 예외 클래스 및 오류 계약

### 7.1 예외 계층

```python
class PrpError(Exception):
    code: str = "PRP_UNKNOWN"
    retryable: bool = False

class PrpDbWriteFailed(PrpError):
    code = "PRP_DB_WRITE_FAILED"
    retryable = True

class PrpDbReadFailed(PrpError):
    code = "PRP_DB_READ_FAILED"
    retryable = True

class PrpInvalidQuery(PrpError):
    code = "PRP_INVALID_QUERY"
    retryable = False

class PrpReportCalcFailed(PrpError):
    code = "PRP_REPORT_CALC_FAILED"
    retryable = False

class PrpSchemaMismatch(PrpError):
    code = "PRP_SCHEMA_MISMATCH"
    retryable = False
```

### 7.2 오류 계약 (LLD 2.3, 7)

```json
{
  "code": "PRP_DB_WRITE_FAILED",
  "message": "이벤트 저장에 실패했습니다.",
  "retryable": true,
  "source": "PRP"
}
```

정책:
- DB write/read 실패: 최대 3회 지수백오프 재시도 후 예외 전파
- 중복 체결(`execution_id`)은 예외가 아닌 멱등 성공 처리
- 부분 집계 실패 시 성공 응답에 `failedTradeCount` 메타를 추가하고 감사로그 기록

## 8. 계산 함수(세금/수수료/손익) 정확 명세

### 8.1 상수

```python
from decimal import Decimal

SELL_TAX_RATE = Decimal("0.002")      # 0.2%
SELL_FEE_RATE = Decimal("0.00011")    # 0.011%
AMOUNT_Q = Decimal("0.01")            # 금액 2자리
RETURN_Q = Decimal("0.0001")          # 수익률 4자리
```

### 8.2 반올림 유틸

```python
from decimal import ROUND_HALF_UP

def q_amount(v: Decimal) -> Decimal:
    return v.quantize(AMOUNT_Q, rounding=ROUND_HALF_UP)

def q_return(v: Decimal) -> Decimal:
    return v.quantize(RETURN_Q, rounding=ROUND_HALF_UP)
```

### 8.3 거래 상세 계산 함수

```python
def calc_buy_amount(buy_price: Decimal, quantity: int) -> Decimal:
    return q_amount(buy_price * Decimal(quantity))

def calc_sell_amount(sell_price: Decimal, quantity: int) -> Decimal:
    return q_amount(sell_price * Decimal(quantity))

def calc_sell_tax(sell_amount: Decimal) -> Decimal:
    return q_amount(sell_amount * SELL_TAX_RATE)

def calc_sell_fee(sell_amount: Decimal) -> Decimal:
    return q_amount(sell_amount * SELL_FEE_RATE)

def calc_net_pnl(buy_amount: Decimal, sell_amount: Decimal, sell_tax: Decimal, sell_fee: Decimal) -> Decimal:
    return q_amount(sell_amount - buy_amount - sell_tax - sell_fee)

def calc_return_rate(net_pnl: Decimal, buy_amount: Decimal) -> Decimal:
    if buy_amount == Decimal("0"):
        raise PrpReportCalcFailed("buyAmount가 0입니다.")
    return q_return((net_pnl / buy_amount) * Decimal("100"))

def calc_trade_detail(buy_price: Decimal, sell_price: Decimal, quantity: int) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
    buy_amount = calc_buy_amount(buy_price, quantity)
    sell_amount = calc_sell_amount(sell_price, quantity)
    sell_tax = calc_sell_tax(sell_amount)
    sell_fee = calc_sell_fee(sell_amount)
    net_pnl = calc_net_pnl(buy_amount, sell_amount, sell_tax, sell_fee)
    return_rate = calc_return_rate(net_pnl, buy_amount)
    return buy_amount, sell_amount, sell_tax, sell_fee, net_pnl, return_rate
```

### 8.4 일일 집계 함수

```python
def aggregate_daily_report(trade_details: list[TradeDetailDTO], trading_date: date, generated_at: datetime) -> DailyReportDTO:
    total_buy_amount = q_amount(sum((d.buy_amount for d in trade_details), Decimal("0")))
    total_sell_amount = q_amount(sum((d.sell_amount for d in trade_details), Decimal("0")))
    total_sell_tax = q_amount(sum((d.sell_tax for d in trade_details), Decimal("0")))
    total_sell_fee = q_amount(sum((d.sell_fee for d in trade_details), Decimal("0")))
    total_net_pnl = q_amount(sum((d.net_pnl for d in trade_details), Decimal("0")))

    if total_buy_amount == Decimal("0"):
        total_return_rate = Decimal("0.0000")
    else:
        total_return_rate = q_return((total_net_pnl / total_buy_amount) * Decimal("100"))

    return DailyReportDTO(
        trading_date=trading_date,
        total_buy_amount=total_buy_amount,
        total_sell_amount=total_sell_amount,
        total_sell_tax=total_sell_tax,
        total_sell_fee=total_sell_fee,
        total_net_pnl=total_net_pnl,
        total_return_rate=total_return_rate,
        generated_at=generated_at,
    )
```

## 9. 구현 절차 (주니어 개발자용)

1. **기본 골격 생성**
   - `src/prp` 하위 폴더/파일 생성(2장 레이아웃 그대로)
   - `bootstrap.py`에서 DB 파일 경로 `runtime/state/prp.db` 상수화

2. **스키마/마이그레이션 구현**
   - `schema.sql` 작성 후 `migration.py`에서 최초 실행 시 적용
   - `schema_version(version=1)` 레코드 기록
   - 앱 시작 시 `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL` 설정

3. **DTO/도메인 타입 작성**
   - 3.2 데이터클래스 구현
   - datetime은 timezone-aware만 허용(naive 입력 시 `PrpInvalidQuery`)

4. **Repository 구현**
   - `EventRepositorySqlite`, `SnapshotRepositorySqlite`, `ReportRepositorySqlite` 작성
   - SQL은 파라미터 바인딩(`?`)만 사용
   - `execution_id` 중복은 `IntegrityError`를 잡아 `False` 반환

5. **직렬화 유틸 구현**
   - payload JSON encode/decode 유틸 작성
   - Decimal/Datetime 변환 규칙 단일화

6. **계산 함수 구현**
   - `formulas.py`에 8장 함수 그대로 구현
   - 반올림 규칙 단위 테스트 작성 (`test_formulas.py`)

7. **서비스 레이어 구현**
   - `PersistenceServiceImpl`: save* 메서드 + 재시도 정책(최대 3회)
   - `ReportServiceImpl`: 체결 매수/매도 페어링 → 상세 계산 → upsert
   - `RecoveryServiceImpl`: 최신 스냅샷 조회/체결 존재조회/복구로그 기록

8. **복구 플로우 연동**
   - 앱 시작부에서 `recoverOnStartup(trading_date)` 실행
   - 스냅샷 복원 후 외부 체결 동기화, 중복체결 무시

9. **테스트**
   - 인메모리 SQLite(`:memory:`)로 repository 테스트
   - 리포트 계산 회귀 테스트(세율/수수료율/반올림 고정)
   - 복구 시 중복 체결 입력 테스트

10. **운영 점검 체크**
   - DB 파일 생성/권한 확인
   - 하루치 샘플 데이터로 `generate_daily_report` 검증
   - 오류 응답 계약(`code/retryable/source`) 일치 확인

## 10. 추적성 매트릭스 (ILD ↔ LLD)

| ILD 항목 | LLD 추적 |
|---|---|
| 모듈 범위/비범위 | LLD 1 |
| DTO/응답 모델 구현 | LLD 2.1, 2.2 |
| 공통 오류 계약/예외 | LLD 2.3, 7.2, 7.3 |
| SQLite 선택 및 DDL 구현 | LLD 3.1, 3.2 |
| 이벤트 영속화 API/멱등 정책 | LLD 4.1 |
| 리포트 생성/조회 흐름 | LLD 4.2 |
| 세금/수수료/손익 계산 함수 | LLD 5 |
| 반올림 정책(2자리/4자리) | LLD 5 |
| 재시작 복구 API/원칙 | LLD 6 |
| 단일 writer, KST 기준 제약 | LLD 7.1 |

## 11. 완료 정의(DoD)

- [ ] `schema.sql` 적용 시 모든 테이블/인덱스 생성 성공
- [ ] saveStrategy/Order/Execution/Snapshot API 정상 동작
- [ ] 중복 `execution_id` 입력 시 실패가 아닌 멱등 성공 처리
- [ ] 거래상세/일일리포트 계산 결과가 LLD 공식과 동일
- [ ] 반올림 규칙(금액2, 수익률4) 테스트 통과
- [ ] 오류 코드/재시도 가능 여부 계약 일치
- [ ] 복구 플로우에서 스냅샷 우선 복원 + 체결 재동기화 동작
- [ ] 문서/코드 모두 한국어 주석/메시지 정책 준수
