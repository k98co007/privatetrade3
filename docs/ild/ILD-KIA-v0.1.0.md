# ILD-KIA v0.1.0

- 문서명: KIA 모듈 구현 상세 설계서 (ILD)
- 버전: v0.1.0
- 작성일: 2026-02-17
- 기반 문서:
  - `docs/lld/LLD-KIA-v0.1.0.md`
  - `docs/hld/HLD-v0.1.0.md` (4.4, 5, 6.2, 8)
  - `docs/srs/SRS-v0.1.0.md` (FR-014, NFR-002, NFR-003, NFR-005)
- 모듈: `KIA` (Kiwoom Integration Adapter)
- 언어/런타임 가정: Python 3.12+, `httpx`(sync/async 모두 적용 가능)

## 1. 구현 범위

LLD-KIA를 실제 구현 단위로 세분화한다.

- 인증/시세/주문/체결 API 호출 클라이언트 구현
- 시세 루프용 배치 시세 조회(`fetch_quotes_batch`) 구현
- 토큰 발급/선제 갱신/강제 갱신(401 대응) 구현
- Mock/Live 모드별 엔드포인트 라우팅 구현
- 실시간(WebSocket) 로그인/등록/해지(`LOGIN`, `REG`, `REMOVE`) 클라이언트 구현
- 재시도/백오프/멱등성 가드 로직 구현
- 외부 오류를 KIA 표준 오류 모델로 매핑 구현

비범위:
- 주문 의사결정(OPM)
- 전략 판단(TSE)
- 시크릿 영속 저장(CSM)

## 1.1 코드 기준 데이터 경로 분리(2026-02-18)

KIA는 상위 모듈의 입력 성격에 따라 아래 두 경로를 분리 제공한다.

- 호가/전략 입력 경로: `fetch_quotes_batch` (TSE 시세 루프 입력)
- 체결/잔고 실시간 경로: `realtime_login/register/receive/remove` (OPM 실행/정합 입력)

제약:
- `realtime_receive`를 호가 스트림 대체로 사용하지 않는다.
- 호가 모니터링 품질 상태(`RUNNING/DEGRADED`) 판단은 TSE 오케스트레이션 책임이다.

## 2. 디렉터리 및 모듈 구조

```text
src/
  kia/
    __init__.py
    contracts.py                 # 외부 노출 DTO/Protocol
    gateway.py                   # KiaGateway 구현체
    endpoint_resolver.py         # mock/live + serviceType URL 결정
    realtime_client.py           # WebSocket LOGIN/REG/REMOVE/수신
    token_provider.py            # 토큰 상태/갱신/single-flight
    api_client.py                # HTTP 공통 호출 래퍼
    retry.py                     # backoff/jitter 정책
    idempotency.py               # clientOrderId 기반 캐시/조회
    error_mapper.py              # http/network/broker 오류 표준화
    models.py                    # 내부 모델(토큰/응답)
    errors.py                    # 예외 계층
```

## 3. 구체 API 클라이언트 시그니처

### 3.1 공통 타입

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Protocol

Mode = Literal["mock", "live"]
ServiceType = Literal["auth", "quote", "order", "execution"]
HttpMethod = Literal["GET", "POST"]
RealtimeType = Literal["00", "04", "0A", "0B", "0C", "0D", "0E", "0F", "0H", "0I", "0J", "0w", "1h"]
```

### 3.2 요청/응답 DTO

```python
@dataclass(frozen=True)
class FetchQuoteRequest:
    mode: Mode
    symbol: str

@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    price: Decimal
    tick_size: int
    as_of: datetime

@dataclass(frozen=True)
class SubmitOrderRequest:
    mode: Mode
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
    mode: Mode
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
    mode: Mode
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
  mode: Mode
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
```

### 3.3 외부 노출 게이트웨이 계약

```python
class KiaGateway(Protocol):
    def fetch_quote(self, req: FetchQuoteRequest) -> MarketQuote: ...
    def fetch_quotes_batch(self, req: PollQuotesRequest) -> PollQuotesResult: ...
    def submit_order(self, req: SubmitOrderRequest) -> OrderResult: ...
    def fetch_execution(self, req: FetchExecutionRequest) -> ExecutionResult: ...
    def fetch_position(self, req: FetchPositionRequest) -> list[PositionSnapshot]: ...
```

### 3.4 내부 API 클라이언트 계약(구체 메서드 시그니처)

```python
@dataclass(frozen=True)
class EndpointInfo:
    base_url: str
    path: str
    method: HttpMethod

@dataclass(frozen=True)
class AccessToken:
    token: str
    issued_at: datetime
    expires_at: datetime
    refresh_at: datetime
    mode: Mode

class EndpointResolver(Protocol):
    def resolve(self, mode: Mode, service_type: ServiceType) -> EndpointInfo: ...

class TokenProvider(Protocol):
    def get_valid_token(self, mode: Mode) -> AccessToken: ...
    def force_refresh(self, mode: Mode) -> AccessToken: ...
    def invalidate(self, mode: Mode) -> None: ...

class KiaApiClient(Protocol):
    def call(
        self,
        *,
        service_type: ServiceType,
        mode: Mode,
        payload: dict[str, Any] | None,
        api_id: str | None = None,
        cont_yn: Literal["N", "Y"] = "N",
        next_key: str = "",
        idempotency_key: str | None = None,
        query: dict[str, str] | None = None,
    ) -> dict[str, Any]: ...

    def fetch_quote_raw(self, *, mode: Mode, symbol: str, api_id: str = "ka10004") -> dict[str, Any]: ...
    def fetch_quotes_batch_raw(self, *, mode: Mode, symbols: list[str], timeout_ms: int, poll_cycle_id: str) -> dict[str, Any]: ...
    def submit_order_raw(self, *, mode: Mode, payload: dict[str, Any], client_order_id: str, api_id: str) -> dict[str, Any]: ...
    def fetch_execution_raw(self, *, mode: Mode, account_no: str, broker_order_id: str) -> dict[str, Any]: ...
    def fetch_position_raw(self, *, mode: Mode, account_no: str, symbol: str | None) -> dict[str, Any]: ...

class KiaRealtimeClient(Protocol):
    def connect(self, *, mode: Mode) -> None: ...
    def login(self, *, access_token: str) -> None: ...
    def register(self, *, group_no: str, refresh: Literal["0", "1"], items: list[str], types: list[RealtimeType]) -> None: ...
    def remove(self, *, group_no: str, items: list[str], types: list[RealtimeType]) -> None: ...
```

## 4. 인증 토큰 갱신 구현 단계

LLD 3장을 코드 흐름으로 고정한다.

1) **초기 조회**: `get_valid_token(mode)` 진입 시 메모리 캐시 조회
2) **선제 갱신 판단**: `now >= refresh_at`이면 갱신 경로 진입
3) **single-flight 락 획득**: 모드별 락(`token-refresh:{mode}`) 사용
4) **이중 확인(double-check)**: 락 획득 후 캐시 재검사(이미 갱신되었는지 확인)
5) **Auth API 호출**: `issue/refresh` 엔드포인트 호출 후 `expires_at`, `refresh_at` 계산
6) **원자적 교체**: 캐시 토큰을 새 토큰으로 교체
7) **호출 진행**: API 호출 헤더에 `Authorization: Bearer <token>` 주입
8) **401 대응**: 첫 401 발생 시 `force_refresh(mode)` 1회 수행 후 동일 요청 1회 재시도
9) **모드 전환 대응**: 모드 변경 이벤트 수신 시 `invalidate(old_mode)` 수행
10) **보안 로깅**: 토큰 원문 로그 금지, 만료시각/모드/traceId만 기록

## 5. Mock/Live 라우팅 구현

### 5.1 라우팅 원칙

- 베이스 URL은 하드코딩 금지, `CSM.resolveKiwoomCredential(mode)` 결과를 신뢰
- 경로/메서드는 `EndpointResolver`가 서비스 단위로 결정
- `mode`는 요청 DTO 필수 필드로 상위 모듈에서 명시 전달

### 5.2 서비스 라우팅 테이블(구현 기준)

| serviceType | protocol | method | mock path | live path | 비고 |
|---|---|---|---|---|---|
| auth | REST | POST | `/oauth2/token` | `/oauth2/token` | `grant_type=client_credentials` |
| quote | REST | POST | `/api/dostk/mrkcond` | `/api/dostk/mrkcond` | `api-id=ka*` |
| order | REST | POST | `/api/dostk/ordr` | `/api/dostk/ordr` | `api-id=kt*` |
| execution | WEBSOCKET | - | `/api/dostk/websocket` | `/api/dostk/websocket` | `LOGIN` 후 `REG/REMOVE` |

> `base_url`/`socket_url`은 모드별로 다르며, REST는 `api-id`로 TR을 구분한다.

### 5.3 구현 의사코드

```text
function resolve(mode, serviceType):
  resolved = csm.resolveKiwoomCredential(mode)
  baseUrl = resolved.base_url

  route = SERVICE_ROUTE_TABLE[serviceType]
  if route is None:
    raise KiaConfigError("KIA_ROUTE_NOT_FOUND")

  return EndpointInfo(
    base_url=baseUrl,
    path=route.path,
    method=route.method,
  )
```

## 6. 재시도/백오프 의사코드

LLD 6장 정책을 그대로 구현한다.

```text
function call_with_retry(serviceType, mode, payload, idempotencyKey=None):
  endpoint = endpointResolver.resolve(mode, serviceType)
  token = tokenProvider.get_valid_token(mode)

  maxAttempts = 3
  baseMs = 200
  maxMs = 2000

  for attempt in 1..maxAttempts:
    try:
      response = http.call(
        method="POST",
        url=endpoint.base_url + endpoint.path,
        headers=build_headers(
          token,
          idempotencyKey,
          apiId=resolveApiId(serviceType, payload),
          contYn=payload.cont_yn or "N",
          nextKey=payload.next_key or "",
        ),
        json=payload,
        timeout=5s,
      )
      return response

    catch err:
      mapped = errorMapper.map(err, serviceType)

      if mapped.code == "KIA_AUTH_TOKEN_EXPIRED" and attempt == 1:
        token = tokenProvider.force_refresh(mode)
        continue

      if mapped.retryable is false:
        raise mapped

      if serviceType == "order" and mapped.code == "KIA_API_TIMEOUT":
        // 무조건 재주문 금지: 멱등 조회 우선
        existing = idempotencyStore.find_or_query(idempotencyKey)
        if existing exists:
          return existing

      if serviceType == "quote_batch" and mapped.code in ["KIA_API_TIMEOUT", "KIA_RATE_LIMITED"]:
        // 시세 루프 지연 누적 방지: 배치 조회는 최대 1회 재시도
        if attempt >= 2:
          raise mapped

      if attempt == maxAttempts:
        raise mapped

      delay = min(baseMs * (2 ^ (attempt - 1)), maxMs) + random(0, 100)
      sleep(delay)
```

WebSocket(실시간) 규칙:

```text
function open_realtime(mode):
  socket = ws.connect(resolveWsUrl(mode) + "/api/dostk/websocket")
  token = tokenProvider.get_valid_token(mode)
  socket.send({"trnm": "LOGIN", "token": token.token})
  socket.send({
    "trnm": "REG",
    "grp_no": "1",
    "refresh": "1",
    "data": [{"item": [""], "type": ["00", "04"]}]
  })
  return socket
```

### 6.2 실시간 실행 경로(코드 1:1)

문서 시퀀스 `LOGIN -> REG -> REMOVE`는 아래 호출 경로로 구현한다.

1) `DefaultKiaGateway.realtime_login(mode)`  
2) `RoutingKiaApiClient.realtime_login_raw(mode)`  
3) `LiveKiaRealtimeClient.login(mode)`  
4) `CsmEndpointResolver.resolve(mode, "realtime")` -> `wss://...:10000/api/dostk/websocket`  
5) `tokenProvider.get_valid_token(mode)` 후 `{"trnm":"LOGIN","token":"..."}` 송신

등록/해지는 동일하게 다음 메서드로 1:1 대응한다.

- 등록: `DefaultKiaGateway.realtime_register` -> `RoutingKiaApiClient.realtime_register_raw` -> `LiveKiaRealtimeClient.register` -> `{"trnm":"REG","grp_no","refresh","data"}`
- 해지: `DefaultKiaGateway.realtime_remove` -> `RoutingKiaApiClient.realtime_remove_raw` -> `LiveKiaRealtimeClient.remove` -> `{"trnm":"REMOVE","grp_no","data"}`

## 6.1 배치 시세 조회 구현 규칙

1) 입력 종목 수 검증: `1 <= len(symbols) <= 20`
2) `poll_cycle_id`는 빈 문자열 불가, 그대로 응답에 반영
3) 종목 단위 호출 실패는 전체 예외로 승격하지 않고 `errors[]`에 누적
4) `quotes`가 일부라도 존재하면 `partial=true` 허용
5) 모든 종목 실패 시 `quotes=[]`, `partial=true`, 오류 코드를 종목별 유지
6) 시세 조회 호출은 서버 부하 제어를 위해 **초당 1건(종목 간 최소 1초 간격)** 강제

의사코드:

```text
function fetch_quotes_batch(req):
  quotes = []
  errors = []

  for symbol in req.symbols:
    rateLimiter.wait("quote", minIntervalMs=1000)
    try:
      raw = api.fetch_quote_raw(mode=req.mode, symbol=symbol)
      quotes.append(map_market_quote(raw))
    catch err:
      mapped = errorMapper.map(err, "quote")
      errors.append({symbol, code: mapped.code, retryable: mapped.retryable})

  partial = len(errors) > 0
  return PollQuotesResult(req.poll_cycle_id, quotes, errors, partial)
```

## 7. 표준 오류 매핑 테이블

### 7.1 표준 오류 모델

```python
@dataclass(frozen=True)
class KiaErrorPayload:
    code: str
    message: str
    retryable: bool
    source: Literal["KIA"]
    details: dict[str, Any] | None = None
```

### 7.2 매핑 규칙 테이블

| 입력 조건 | 표준 코드 | retryable | message(표준) |
|---|---|---:|---|
| HTTP 401 또는 브로커 토큰만료 코드 | `KIA_AUTH_TOKEN_EXPIRED` | true | 인증 토큰이 만료되었습니다. |
| HTTP 403 | `KIA_AUTH_FORBIDDEN` | false | API 권한이 없습니다. |
| HTTP 404 (종목/리소스 없음) | `KIA_QUOTE_SYMBOL_NOT_FOUND` | false | 요청한 종목 또는 리소스를 찾을 수 없습니다. |
| HTTP 409 (중복 주문) | `KIA_ORDER_DUPLICATED` | false | 동일 멱등키의 주문이 이미 처리되었습니다. |
| HTTP 429 | `KIA_RATE_LIMITED` | true | 호출 한도를 초과했습니다. 잠시 후 재시도하세요. |
| HTTP 5xx | `KIA_UPSTREAM_UNAVAILABLE` | true | 외부 거래 API가 일시적으로 불안정합니다. |
| 네트워크 타임아웃/연결 끊김 | `KIA_API_TIMEOUT` | true | 거래 API 응답 시간이 초과되었습니다. |
| JSON 파싱 실패/스키마 불일치 | `KIA_RESPONSE_INVALID` | false | 거래 API 응답 형식이 올바르지 않습니다. |
| route/service 설정 누락 | `KIA_ROUTE_NOT_FOUND` | false | 라우팅 설정을 찾을 수 없습니다. |
| 그 외 미분류 예외 | `KIA_UNKNOWN` | false | 알 수 없는 오류가 발생했습니다. |

## 8. 구현 순서(권장)

1. `contracts.py`, `models.py`, `errors.py` 작성
2. `endpoint_resolver.py` + 서비스 라우팅 테이블 작성
3. `token_provider.py`(single-flight 포함) 작성
4. `error_mapper.py` 작성
5. `retry.py` 작성
6. `api_client.py` 작성
7. `idempotency.py` 작성
8. `gateway.py`에서 DTO 변환/조립

## 9. 테스트 포인트

- 토큰 선제 갱신(`now >= refresh_at`) 검증
- 401 수신 시 강제 갱신 후 단 1회 재시도 검증
- mock/live 모드 전환 시 URL 및 토큰 캐시 분리 검증
- 429/5xx/timeout 재시도 및 지수 백오프 범위 검증
- 주문 timeout 시 재주문 대신 `client_order_id` 조회 우선 검증
- 오류 매핑 테이블과 코드 일치성 검증
- `fetch_quotes_batch` 부분성공(`partial=true`) 반환 검증
- 배치 조회 연속 timeout/429에서 1회 재시도 후 종료 검증
- `poll_cycle_id` 입력/출력 동일성 및 종목별 오류 코드 보존 검증
- 시세 조회 호출 간 최소 1초 간격(초당 1건) 강제 검증

## 10. 결론

본 ILD-KIA는 LLD-KIA를 개발 가능한 수준의 구현 계약(구체 메서드 시그니처, 토큰 갱신 단계, 모드 라우팅, 재시도/백오프 의사코드, 표준 오류 매핑 테이블)으로 상세화하였다.

## 11. 구현 반영 상태(추적표)

- 업데이트 일자: 2026-02-19
- 상태 기준: `완료`(코드 + 테스트 반영), `부분`(코드만 또는 테스트만)

| ILD 항목 | 상태 | 구현 위치 | 검증 위치 |
|---|---|---|---|
| `fetch_quotes_batch` DTO/계약 추가 | 완료 | `src/kia/contracts.py`, `src/kia/__init__.py` | `tests/test_kia.py::test_fetch_quotes_batch_returns_partial_with_symbol_errors` |
| 배치 시세 입력 검증(`1<=symbols<=20`, `poll_cycle_id` 비어있음 금지) | 완료 | `src/kia/gateway.py` | `tests/test_kia.py::test_fetch_quotes_batch_validates_input` |
| 배치 시세 부분성공(`errors[]`, `partial=true`) | 완료 | `src/kia/gateway.py`, `src/kia/api_client.py` | `tests/test_kia.py::test_fetch_quotes_batch_returns_partial_with_symbol_errors` |
| 시세 조회 초당 1건 제한(종목 간 최소 1초) | 완료 | `src/kia/api_client.py` | `tests/test_kia.py::test_fetch_quotes_batch_enforces_one_request_per_second` |
| 배치 조회 timeout/429 시 최대 1회 재시도 후 종료 | 완료 | `src/kia/api_client.py` | `tests/test_kia.py::test_fetch_quotes_batch_timeout_or_429_retries_only_once` |
| 주문 timeout 시 재주문 대신 멱등 조회 우선 | 완료 | `src/kia/idempotency.py`, `src/kia/api_client.py` | `tests/test_kia.py::test_order_timeout_uses_idempotency_cache_instead_of_retrying_order` |
| 401 수신 시 강제 갱신 후 1회 재시도 | 완료 | `src/kia/api_client.py`, `src/kia/token_provider.py` | `tests/test_kia.py::test_live_quote_401_triggers_single_force_refresh_and_retry` |
| 모드 전환 시 이전 모드 토큰 무효화 | 완료 | `src/kia/api_client.py` | `tests/test_kia.py::test_mode_switch_invalidates_previous_mode_token_cache` |
| Mock/Live 라우팅(REST/WS 경로 결정) | 완료 | `src/kia/endpoint_resolver.py`, `src/kia/realtime_client.py` | `tests/test_kia.py::test_realtime_login_register_remove_execution_path` |
| 표준 오류 매핑(401/403/404/409/429/5xx/timeout/invalid) | 완료 | `src/kia/error_mapper.py`, `src/kia/errors.py` | `tests/test_kia.py::test_live_429_is_mapped_and_retried`, `tests/test_kia.py::test_realtime_login_failure_is_mapped` |
| `fetch_position` DTO/게이트웨이/API 시그니처 정합 | 완료 | `src/kia/contracts.py`, `src/kia/gateway.py`, `src/kia/api_client.py`, `src/kia/__init__.py` | (추가 단위 테스트 가능) |

### 11.1 회귀 확인

- KIA 단위 테스트: `pytest tests/test_kia.py -q` 통과
- 전체 테스트: `pytest -q` 통과
