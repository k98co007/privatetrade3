# ILD-UAG v0.1.0

- 문서명: UAG 모듈 구현 상세 설계서 (ILD)
- 버전: v0.1.0
- 작성일: 2026-02-17
- 기반 문서:
  - `docs/lld/LLD-UAG-v0.1.0.md`
  - `docs/lld/LLD-CSM-v0.1.0.md`
  - `docs/lld/LLD-OPM-v0.1.0.md`
  - `docs/lld/LLD-PRP-v0.1.0.md`
  - `docs/lld/LLD-TSE-v0.1.0.md`
  - `docs/hld/HLD-v0.1.0.md`
  - `docs/srs/SRS-v0.1.0.md`
- 모듈: `UAG` (UI/API Gateway)
- 런타임 가정: Python 3.12+, 단일 프로세스, REST + SSE

## 1. 구현 범위

LLD-UAG의 API 계약을 실제 구현 단위(라우터/스키마/유효성 검증/프론트 연동)로 구체화한다.

- 설정 조회/저장, 모드 전환, 투자 시작/중지, 모니터링 조회, 리포트 조회 API 구현
- 공통 응답 계약(`success/requestId/meta`) 및 표준 오류 계약(`error.code/details[]`) 강제
- 입력 검증 스키마(JSON Schema + 런타임 검증) 정의
- 모니터링 전송 방식(Polling/SSE) 구현 옵션 정의
- 프론트엔드 API 클라이언트/상태동기화 흐름 정의

비범위:
- 전략 판정 로직(TSE)
- 주문 체결 처리(OPM/KIA)
- 리포트 집계 계산(PRP)

## 2. 디렉터리/모듈 구조 제안

```text
src/
  uag/
    __init__.py
    bootstrap.py

    api/
      __init__.py
      router_settings.py
      router_mode.py
      router_trading.py
      router_monitoring.py
      router_reports.py
      router_session.py

    schemas/
      __init__.py
      common.py              # SuccessEnvelope, ErrorEnvelope, Meta
      settings.py            # SettingsSaveRequest/Response
      mode.py                # ModeSwitchRequest/Response
      trading.py             # Start/Stop request/response
      monitoring.py          # SnapshotResponse, SseEventPayload
      reports.py             # DailyReportResponse, TradeReportResponse

    validation/
      __init__.py
      symbol_rules.py        # 종목코드/중복/개수 검증
      mode_rules.py          # 모드 전환/라이브 확인 검증
      credential_rules.py    # 계좌/자격정보 검증
      date_rules.py          # YYYY-MM-DD 검증

    service/
      __init__.py
      settings_service.py
      mode_service.py
      trading_service.py
      monitoring_service.py
      report_service.py

    gateway/
      __init__.py
      csm_gateway.py
      tse_gateway.py
      opm_gateway.py
      prp_gateway.py

    security/
      __init__.py
      session_manager.py
      csrf_guard.py
      masking.py

    sse/
      __init__.py
      event_bus.py           # 메모리 pub/sub
      event_mapper.py        # 도메인 이벤트 -> SSE payload
      stream_handler.py      # keepalive/재연결/Last-Event-ID

    errors/
      __init__.py
      error_codes.py
      exceptions.py
      exception_mapper.py

tests/
  uag/
    test_settings_validation.py
    test_mode_switch_guard.py
    test_trading_start_stop.py
    test_monitoring_snapshot.py
    test_reports_query.py
    test_sse_stream.py
```

## 3. API 엔드포인트 시그니처

## 3.1 서버 라우터 시그니처 (Python)

```python
from datetime import date
from typing import Annotated, Literal

Mode = Literal["mock", "live"]

# settings
async def get_settings(session_id: Annotated[str, "uag.sid"]) -> dict: ...
async def save_settings(
    body: "SettingsSaveRequest",
    session_id: Annotated[str, "uag.sid"],
    csrf_token: Annotated[str, "X-CSRF-Token"],
) -> dict: ...

# mode
async def switch_mode(
    body: "ModeSwitchRequest",
    session_id: Annotated[str, "uag.sid"],
    csrf_token: Annotated[str, "X-CSRF-Token"],
) -> dict: ...

# trading
async def start_trading(
    body: "StartTradingRequest",
    session_id: Annotated[str, "uag.sid"],
    csrf_token: Annotated[str, "X-CSRF-Token"],
) -> dict: ...

async def stop_trading(
    body: "StopTradingRequest",
    session_id: Annotated[str, "uag.sid"],
    csrf_token: Annotated[str, "X-CSRF-Token"],
) -> dict: ...

# monitoring
async def get_monitoring_snapshot(
    include: str | None,
    session_id: Annotated[str, "uag.sid"],
) -> dict: ...

async def stream_monitoring_events(
    last_event_id: str | None,
    session_id: Annotated[str, "uag.sid"],
): ...

# reports
async def get_daily_report(
    trading_date: date,
    session_id: Annotated[str, "uag.sid"],
) -> dict: ...

async def get_trades_report(
    trading_date: date,
    symbol: str | None,
    session_id: Annotated[str, "uag.sid"],
) -> dict: ...
```

## 3.2 프론트 API 클라이언트 시그니처 (TypeScript)

```ts
export type Mode = "mock" | "live";

export interface UagApiClient {
  getSettings(): Promise<SettingsResponse>;
  saveSettings(req: SettingsSaveRequest): Promise<SettingsSaveResponse>;
  switchMode(req: ModeSwitchRequest): Promise<ModeSwitchResponse>;
  startTrading(req: StartTradingRequest): Promise<StartTradingResponse>;
  stopTrading(req: StopTradingRequest): Promise<StopTradingResponse>;
  getMonitoringSnapshot(include?: string[]): Promise<MonitoringSnapshotResponse>;
  openMonitoringSse(onEvent: (event: MonitoringEvent) => void): () => void;
  getDailyReport(tradingDate: string): Promise<DailyReportResponse>;
  getTradesReport(tradingDate: string, symbol?: string): Promise<TradesReportResponse>;
}
```

## 4. 입력 검증 스키마

## 4.1 SettingsSaveRequest

```json
{
  "$id": "SettingsSaveRequest",
  "type": "object",
  "required": ["watchSymbols", "mode", "liveModeConfirmed", "credential"],
  "additionalProperties": false,
  "properties": {
    "watchSymbols": {
      "type": "array",
      "minItems": 1,
      "maxItems": 20,
      "uniqueItems": true,
      "items": {
        "type": "string",
        "pattern": "^[0-9]{6}$"
      }
    },
    "mode": {
      "type": "string",
      "enum": ["mock", "live"]
    },
    "liveModeConfirmed": { "type": "boolean" },
    "credential": {
      "type": "object",
      "required": ["appKey", "appSecret", "accountNo", "userId"],
      "additionalProperties": false,
      "properties": {
        "appKey": { "type": "string", "minLength": 1, "maxLength": 128 },
        "appSecret": { "type": "string", "minLength": 1, "maxLength": 256 },
        "accountNo": { "type": "string", "pattern": "^[0-9-]+$", "minLength": 8, "maxLength": 32 },
        "userId": { "type": "string", "minLength": 1, "maxLength": 64 }
      }
    }
  },
  "allOf": [
    {
      "if": {
        "properties": { "mode": { "const": "live" } },
        "required": ["mode"]
      },
      "then": {
        "properties": { "liveModeConfirmed": { "const": true } }
      }
    }
  ]
}
```

## 4.2 ModeSwitchRequest

```json
{
  "$id": "ModeSwitchRequest",
  "type": "object",
  "required": ["targetMode", "liveModeConfirmed"],
  "additionalProperties": false,
  "properties": {
    "targetMode": { "type": "string", "enum": ["mock", "live"] },
    "liveModeConfirmed": { "type": "boolean" }
  },
  "allOf": [
    {
      "if": {
        "properties": { "targetMode": { "const": "live" } },
        "required": ["targetMode"]
      },
      "then": {
        "properties": { "liveModeConfirmed": { "const": true } }
      }
    }
  ]
}
```

## 4.3 StartTradingRequest / StopTradingRequest

```json
{
  "$id": "StartTradingRequest",
  "type": "object",
  "required": ["tradingDate"],
  "additionalProperties": false,
  "properties": {
    "tradingDate": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$" },
    "dryRun": { "type": "boolean", "default": false }
  }
}
```

```json
{
  "$id": "StopTradingRequest",
  "type": "object",
  "required": ["reason"],
  "additionalProperties": false,
  "properties": {
    "reason": {
      "type": "string",
      "enum": ["user_request", "session_timeout", "safety_guard", "shutdown"]
    }
  }
}
```

## 4.4 쿼리 검증 규칙

- `include`: `watch,orders,position,strategy,engine` 중 콤마 구분 집합
- `tradingDate`: `YYYY-MM-DD`
- `symbol`: 선택값, 제공 시 `^[0-9]{6}$`

## 5. 응답 계약(Response Contracts)

## 5.1 공통 Envelope

```json
{
  "success": true,
  "requestId": "req-20260217-0001",
  "data": {},
  "meta": {
    "timestamp": "2026-02-17T09:10:00+09:00"
  }
}
```

오류 Envelope:

```json
{
  "success": false,
  "requestId": "req-20260217-0002",
  "error": {
    "code": "UAG_VALIDATION_ERROR",
    "message": "입력값 검증에 실패했습니다.",
    "retryable": false,
    "source": "UAG",
    "details": [
      { "field": "watchSymbols[0]", "reason": "6자리 숫자 형식이 아닙니다." }
    ]
  },
  "meta": {
    "timestamp": "2026-02-17T09:10:01+09:00"
  }
}
```

## 5.2 엔드포인트별 `data` 계약

- `GET /api/v1/settings`: `watchSymbols[]`, `mode`, `liveModeConfirmed`, `credentialMasked`
- `POST /api/v1/settings`: `configVersion`, `updatedAt`, 저장 결과 + `credentialMasked`
- `POST /api/v1/mode/switch`: `mode`, `updatedAt`
- `POST /api/v1/trading/start`: `engineState=STARTING`, `acceptedAt`
- `POST /api/v1/trading/stop`: `engineState=STOPPING`, `acceptedAt`
- `GET /api/v1/monitoring/snapshot`: `engineState`, `asOf`, `watch[]`, `orders[]`, `position`, `strategy`
- `GET /api/v1/reports/daily`: 일자 집계 필드(`totalBuyAmount`, `totalNetPnl`, `totalReturnRate` 등)
- `GET /api/v1/reports/trades`: `items[]` 체결 상세 목록

## 6. 요청 예시(정확 사양)

공통 헤더(상태 변경 API):
- `Cookie: uag.sid=<session-id>`
- `X-CSRF-Token: <csrf-token>`
- `Content-Type: application/json`

## 6.1 설정 저장 (Settings Save)

```http
POST /api/v1/settings HTTP/1.1
Host: 127.0.0.1:8000
Cookie: uag.sid=sid-abc123
X-CSRF-Token: csrf-xyz890
Content-Type: application/json

{
  "watchSymbols": ["005930", "000660", "035420"],
  "mode": "mock",
  "liveModeConfirmed": false,
  "credential": {
    "appKey": "demo-app-key",
    "appSecret": "demo-app-secret",
    "accountNo": "1234-56-7890",
    "userId": "demoUser"
  }
}
```

## 6.2 모드 전환 (Mode Switch)

```http
POST /api/v1/mode/switch HTTP/1.1
Host: 127.0.0.1:8000
Cookie: uag.sid=sid-abc123
X-CSRF-Token: csrf-xyz890
Content-Type: application/json

{
  "targetMode": "live",
  "liveModeConfirmed": true
}
```

## 6.3 투자 시작 (Start Trading)

```http
POST /api/v1/trading/start HTTP/1.1
Host: 127.0.0.1:8000
Cookie: uag.sid=sid-abc123
X-CSRF-Token: csrf-xyz890
Content-Type: application/json

{
  "tradingDate": "2026-02-17",
  "dryRun": false
}
```

## 6.4 모니터 상태 조회 (Monitor Status)

Polling:

```http
GET /api/v1/monitoring/snapshot?include=watch,orders,position,strategy,engine HTTP/1.1
Host: 127.0.0.1:8000
Cookie: uag.sid=sid-abc123
Accept: application/json
```

SSE:

```http
GET /api/v1/monitoring/events HTTP/1.1
Host: 127.0.0.1:8000
Cookie: uag.sid=sid-abc123
Accept: text/event-stream
Cache-Control: no-cache
Last-Event-ID: evt-12031
```

## 6.5 리포트 조회 (Report Query)

일자 요약:

```http
GET /api/v1/reports/daily?tradingDate=2026-02-17 HTTP/1.1
Host: 127.0.0.1:8000
Cookie: uag.sid=sid-abc123
Accept: application/json
```

체결 상세:

```http
GET /api/v1/reports/trades?tradingDate=2026-02-17&symbol=005930 HTTP/1.1
Host: 127.0.0.1:8000
Cookie: uag.sid=sid-abc123
Accept: application/json
```

## 7. SSE / Polling 구현 옵션

## 7.1 옵션 A: Polling 중심 + SSE 보조(권장)

- UI 기본 갱신: `GET /monitoring/snapshot` 2초 주기
- 이벤트 신호: SSE 수신 시 즉시 snapshot 재조회(지연/누락 회복)
- 장점: 구현 단순, 일시 끊김 복구 용이, 데이터 일관성 높음
- 단점: snapshot 요청 수 증가

## 7.2 옵션 B: SSE 중심 + Polling fallback

- UI 기본 갱신: SSE 이벤트 payload 직접 반영
- fallback: 10초마다 snapshot 무결성 점검
- 장점: 트래픽 효율
- 단점: 프론트 상태머신 복잡도 상승

## 7.3 SSE 프로토콜 상세

- heartbeat: 5초 (`event: heartbeat`)
- 권장 재연결 대기: `retry: 3000`
- 이벤트 ID: `evt-{epochMillis}-{seq}`
- 지원 이벤트: `engine`, `strategy`, `order`, `position`, `heartbeat`
- 재연결 시 `Last-Event-ID` 사용, 서버 버퍼 미보유 구간은 snapshot 강제 재동기화

SSE 메시지 예시:

```text
id: evt-1763322310000-15
event: strategy
retry: 3000
data: {"occurredAt":"2026-02-17T09:05:10+09:00","symbol":"005930","eventType":"BUY_SIGNAL","reboundRate":0.2128}

```

## 8. 프론트엔드 연동 흐름

## 8.1 앱 초기화

1) `GET /api/v1/settings` 호출
2) 성공 시 설정 화면 초기 상태 구성(자격정보는 마스킹 문자열만 표시)
3) `GET /api/v1/monitoring/snapshot?include=engine`로 엔진 상태 확인
4) 엔진 RUNNING이면 모니터 화면 자동 진입 + SSE 연결

## 8.2 설정 저장/모드 전환

1) 폼 로컬 검증(종목 수, 중복, 모드/live 확인)
2) `POST /settings` 또는 `POST /mode/switch` 호출
3) 성공 시 서버 반환 `credentialMasked`로 상태 교체
4) 실패 시 `error.details[]`를 필드별 에러로 매핑

## 8.3 트레이딩 시작/모니터링

1) `POST /trading/start` 호출 후 `202 STARTING` 수신
2) SSE 연결(`GET /monitoring/events`) + snapshot 2초 polling 시작
3) `engineState == RUNNING` 전환 시 버튼 상태(`시작` 비활성/`중지` 활성) 업데이트
4) SSE 끊김 시 자동 재연결(최대 5회), 실패 시 polling-only로 강등

## 8.4 리포트 조회

1) 날짜 선택 후 `GET /reports/daily`
2) 필요 시 심볼 필터 포함 `GET /reports/trades`
3) 합계/목록 동시 표시, 조회 오류 시 기존 화면 유지 + 토스트 오류 노출

## 9. 오류 코드/HTTP 매핑

| HTTP | 코드 | 의미 | retryable |
|---|---|---|---|
| 400 | UAG_VALIDATION_ERROR | 입력 형식/스키마 오류 | false |
| 400 | UAG_DATE_FORMAT_INVALID | 날짜 형식 오류 | false |
| 401 | UAG_SESSION_REQUIRED | 세션 없음/만료 | false |
| 403 | UAG_CSRF_INVALID | CSRF 토큰 오류 | false |
| 409 | UAG_ENGINE_ALREADY_RUNNING | 중복 시작 | false |
| 409 | UAG_ENGINE_ALREADY_STOPPED | 중복 중지 | false |
| 503 | UAG_DOWNSTREAM_TEMPORARY | 하위 모듈 일시 장애 | true |
| 500 | UAG_INTERNAL_ERROR | 미처리 내부 예외 | false |

## 10. 구현 체크리스트

- [x] 엔드포인트 시그니처 구체화
- [x] 입력 스키마/검증 규칙 정의
- [x] 공통 응답/오류 계약 정의
- [x] 상태 변경 API CSRF 강제
- [x] Polling/SSE 구현 옵션 명세
- [x] 프론트 연동 플로우 정의
- [x] 정확한 요청 예시(설정 저장/모드 전환/투자 시작/모니터/리포트) 포함
- [x] 한국어 작성
