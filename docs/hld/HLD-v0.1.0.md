# HLD v0.1.0

- 문서명: 고수준 설계서 (HLD)
- 버전: v0.1.0
- 작성일: 2026-02-17
- 기반 문서: `docs/srs/SRS-v0.1.0.md`
- 적용 범위: 키움 REST API 기반 개인 자동매매 시스템(개인용 PC 서버 + 웹브라우저)

## 1. 시스템 아키텍처 개요

본 시스템은 **웹브라우저 UI**와 **개인용 PC 서버 애플리케이션**으로 구성된다.

- 브라우저는 설정 입력(종목, 모의/실전, 자격정보), 시작 명령, 모니터링/결과 조회를 제공한다.
- 개인용 PC 서버는 장중 시세 지속 조회 루프, 전략 판정, 주문 실행, 체결/포지션 관리, 리포트 계산/저장을 담당한다.
- 외부 연동은 키움 OpenAPI 규약으로 단일화한다(REST: 인증/시세/주문, WebSocket: 실시간 주문체결/시세).
- 로컬 저장소는 Git 비추적 경로에 설정/운영상태/리포트를 저장한다.

아키텍처 스타일은 **UI-서비스-인프라 레이어 기반 모듈형 모놀리식**으로 정의하며, 추후 모듈 단위 LLD/테스트 티켓 분할이 가능하도록 인터페이스 경계를 명확히 둔다.

## 2. 배포 아키텍처(개인용 PC 서버 + 웹브라우저)

### 2.1 배포 노드

- **Node A: 개인용 PC 서버 프로세스**
  - 실행 위치: 사용자 집 PC
  - 역할: 전략 엔진, API 연동, 상태/리포트 저장, UI API 제공
- **Node B: 웹브라우저(동일 PC 또는 로컬 네트워크 클라이언트)**
  - 역할: 사용자 인터페이스
- **Node C: 키움 OpenAPI(외부 시스템)**
  - 역할: 인증/시세/주문/체결 데이터 제공

### 2.2 연결 방식

- 브라우저 ↔ 개인용 PC 서버: HTTP(S) + 주기적 폴링(또는 SSE)
- 개인용 PC 서버 ↔ 키움 OpenAPI: HTTPS REST + WSS(WebSocket)
- 개인용 PC 서버 ↔ 로컬 저장소: 파일 I/O (Git 비추적 디렉터리)

### 2.3 운영 가정

- 장중 기준 시각(09:03)은 개인용 PC 서버 시스템 시각을 사용한다.
- 서버 재시작 시 마지막 저장 스냅샷 기준으로 복구한다.

### 2.4 장중 시세 지속 조회 루프(필수)

자동매매 실행 중에는 서버 내부에 **종료될 때까지 지속되는 시세 조회 루프**가 반드시 존재해야 한다.

- 루프 소유 모듈: `TSE`(오케스트레이션) + `KIA`(시세 API 호출)
- 시작/종료 트리거: `UAG`의 `StartTradingCommand` / `StopTradingCommand`
- 동작: 감시 종목(1~20개)을 주기적으로 조회하여 `MarketQuote` 이벤트를 `TSE` 상태머신 입력으로 전달
- 주기 파라미터: `quote_poll_interval_ms`, `quote_poll_timeout_ms`, `quote_error_retry_max` (구체값은 LLD에서 확정)
- 보호 규칙: 루프 정지/지연 임계치 초과 시 신규 매수 신호 차단, 상태를 `DEGRADED`로 전환
- 복구 규칙: API 정상화 시 루프를 자동 재개하고 `DEGRADED -> RUNNING`으로 전환

## 3. Module Decomposition (명확한 모듈 목록과 약칭)

총 6개 모듈로 분해한다.

1. **UI/API Gateway (`UAG`)**
2. **Trading Strategy Engine (`TSE`)**
3. **Order & Position Manager (`OPM`)**
4. **Kiwoom Integration Adapter (`KIA`)**
5. **Configuration & Secret Manager (`CSM`)**
6. **Persistence & Reporting (`PRP`)**

모듈 분해 원칙:
- SRS 기능군(FR-001~017)을 책임 단위로 분리
- 외부 의존(키움 API, 파일 저장)을 경계 모듈로 격리
- LLD/테스트 티켓이 모듈별로 독립 진행 가능하도록 입출력 계약 고정

## 4. 각 모듈 책임/입출력/의존성

### 4.1 `UAG` (UI/API Gateway)

- 책임
  - 웹 UI 요청 수신/검증/응답
  - 투자 시작/상태 조회/리포트 조회 API 제공
  - 자격정보 입력 시 마스킹 정책 적용
- 입력
  - 사용자 HTTP 요청(설정 저장, 모드 전환, 투자 시작, 모니터링 조회)
- 출력
  - JSON 응답(설정 결과, 상태 스냅샷, 리포트 데이터)
- 의존성
  - `CSM` (설정 조회/저장)
  - `TSE` (전략 실행 제어)
  - `PRP` (리포트/상태 조회)

### 4.2 `TSE` (Trading Strategy Engine)

- 책임
  - 09:03 기준가 확정(FR-002)
  - -1% 하락 감지/전저점 추적/0.2% 반등 판정(FR-003~005)
  - +1% 최소수익확보, 최고수익률/이익보전율 80% 매도 판정(FR-008~011)
  - 단일 종목 전액 매수 및 추가 매수 차단(FR-006~007)
- 입력
  - 시세 이벤트(루프 주기 기반 종목 현재가)
  - 주문/체결 상태
  - 감시 종목/모드/전략 고정 파라미터
- 출력
  - 전략 신호(`BUY_SIGNAL`, `SELL_SIGNAL`)
  - 상태 변화 이벤트(후보 진입, 최소수익확보, 매도 트리거)
- 의존성
  - `OPM` (주문 실행 요청)
  - `PRP` (전략 상태 저장)

### 4.3 `OPM` (Order & Position Manager)

- 책임
  - 매수/매도 주문 생성 및 주문 수명주기 관리
  - 보유 포지션/평단/수익률 상태 관리
  - 매도 주문가 `현재가-2틱` 산정(FR-011)
- 입력
  - `TSE` 전략 신호
  - 체결/잔고 조회 결과
- 출력
  - 주문 요청 DTO
  - 포지션 스냅샷
- 의존성
  - `KIA` (주문 제출/체결 조회)
  - `PRP` (주문/체결 이벤트 저장)

### 4.4 `KIA` (Kiwoom Integration Adapter)

- 책임
  - 키움 REST API 인증 토큰 발급/갱신
  - 시세/주문 REST 호출 캡슐화(`POST /api/dostk/mrkcond`, `POST /api/dostk/ordr`)
  - 실시간 채널(WebSocket) 캡슐화(`wss://.../api/dostk/websocket`, `LOGIN` -> `REG/REMOVE`)
  - REST 공통 헤더 규약 적용(`authorization`, `api-id`, `cont-yn`, `next-key`)
  - 시세 루프용 단건/배치 조회 계약 제공 및 호출 제한 준수
  - 모의/실전 엔드포인트 라우팅(FR-014)
  - 외부 API 오류 표준화
- 입력
  - 내부 표준 요청 DTO(시세조회/주문/체결조회)
  - 운영 모드(Mock/Live)
- 출력
  - 내부 표준 응답 DTO
  - 오류 코드/오류 메시지(민감정보 제외)
- 의존성
  - `CSM` (자격정보 및 모드)

### 4.5 `CSM` (Configuration & Secret Manager)

- 책임
  - 감시 종목(1~20), 모드(Mock/Live), 자격정보 저장/조회
  - Git 비추적 설정 파일 관리(FR-013)
  - 설정 유효성 검증 및 기본값 로딩
- 입력
  - UI 설정 변경 요청
- 출력
  - 런타임 설정 스냅샷
- 의존성
  - `PRP` 또는 파일 I/O 추상화(로컬 저장)

### 4.6 `PRP` (Persistence & Reporting)

- 책임
  - 주문/체결/전략 이벤트 영속화(NFR-005)
  - 재시작 복구용 상태 스냅샷 저장/복원(NFR-003)
  - 일자별 리포트 계산/조회(FR-016~017)
- 입력
  - 주문/체결 이벤트, 포지션 상태, 전략 상태
- 출력
  - `DailyReport`, `TradeDetail`, 운영 로그
- 의존성
  - 로컬 파일 저장소(JSON/CSV/SQLite 중 1개 기술선택은 LLD에서 확정)

## 5. 모듈 간 인터페이스 계약

### 5.1 계약 원칙

- 모듈 간 통신은 **명시적 DTO**를 사용한다.
- 시간/가격/수익률 필드 단위와 반올림 규칙은 전역 공통 유틸로 통일한다.
- 장애 전파는 공통 오류 모델(`code`, `message`, `retryable`, `source`)을 따른다.

### 5.2 주요 계약

- `UAG -> CSM`: `SaveSettingsRequest`, `GetSettingsResponse`
- `UAG -> TSE`: `StartTradingCommand`, `StopTradingCommand`
- `TSE -> KIA`: `PollQuotesRequest`, `PollQuotesResult`
- `TSE -> OPM`: `PlaceBuyOrderCommand`, `PlaceSellOrderCommand`
- `OPM -> KIA`: `SubmitOrderRequest`, `FetchExecutionRequest`
- `KIA -> OPM/TSE`: `MarketQuote`, `OrderResult`, `ExecutionResult`
- `OPM/TSE -> PRP`: `StrategyEvent`, `OrderEvent`, `ExecutionEvent`, `PositionSnapshot`
- `UAG -> PRP`: `GetDailyReportQuery`, `GetTradeDetailsQuery`

### 5.3 계약 안정성(LLD 분할 기준)

다음 항목은 v0.1.0에서 변경 금지 계약으로 간주한다.
- 모듈 약칭/책임 경계
- 전략 임계치 파라미터 의미(1%, 0.2%, 1%, 80%, -2틱)
- `DailyReport` 계산식 필드 정의

## 6. 장애/복구 개요

### 6.1 장애 유형

- 외부 API 장애: 인증 실패, 시세/주문 API 타임아웃, 5xx 오류
- 로컬 장애: 저장 실패, 파일 손상, 프로세스 중단/재시작
- 데이터 장애: 체결 누락/중복 이벤트

### 6.2 복구 전략

- API 호출 재시도: 지수 백오프 + 최대 재시도 횟수 제한
- 주문 계열 요청: 멱등 키(클라이언트 주문키) 기반 중복 방지
- 시세 루프 복구: 연속 실패 임계치 도달 시 `DEGRADED`, 정상 응답 회복 시 자동 `RUNNING` 복귀
- 상태 복구: 재시작 시 `PRP` 마지막 스냅샷 복원 후 `KIA` 체결/잔고 재동기화
- 장애 격리: `KIA` 오류는 표준 오류로 변환해 상위 모듈 영향 최소화

### 6.3 운영 알림

- 치명 장애(주문 실패, 인증 실패 지속)는 UI 상태 배너/에러 코드로 노출
- 민감정보(앱키, 시크릿)는 로그/알림에 출력 금지

## 7. 보안/설정관리(.gitignore 대상 config)

### 7.1 민감정보 저장 정책

- 자격정보는 로컬 파일에만 저장하며 Git 추적 제외한다.
- 권장 경로 예시: `runtime/config/credentials.local.json`
- 저장 시 필드 단위 암호화 또는 OS 보호 저장소 사용은 LLD에서 선택한다.

### 7.2 .gitignore 정책

필수 제외 대상:
- `runtime/config/*.local.json`
- `runtime/secrets/**`
- `runtime/state/**`
- `runtime/reports/**`
- `logs/**`

### 7.3 로그/마스킹 정책

- 자격정보 필드는 저장/조회/오류 모두 마스킹 표시
- 주문/체결 로그는 감사 가능성 유지하되 민감정보 제거

## 8. 운영 모드 전환(Mock/Live)

### 8.1 모드 정의

- **Mock 모드**: 모의투자 Host 사용 (`https://mockapi.kiwoom.com`, `wss://mockapi.kiwoom.com:10000`)
- **Live 모드**: 실전 Host 사용 (`https://api.kiwoom.com`, `wss://api.kiwoom.com:10000`)

### 8.2 전환 규칙

- 모드는 `CSM` 단일 소스로 저장/조회한다.
- `KIA`는 모든 외부 호출 시 현재 모드 기준 엔드포인트를 선택한다.
- 모드 전환은 비거래 상태(미체결 주문 없음, 포지션 없음)에서만 허용하는 것을 기본 정책으로 한다.

### 8.3 안전장치

- Live 진입 시 확인 플래그(예: `live_mode_confirmed=true`) 필요
- 현재 모드는 UI 상단 고정 배지로 항상 노출

### 8.4 키움 프로토콜 고정 규약

- 시세/주문 REST는 endpoint 분기보다 `api-id(TR)` 기준으로 동작한다.
  - 시세: `api-id=ka*`, URL=`/api/dostk/mrkcond`
  - 주문: `api-id=kt*`, URL=`/api/dostk/ordr`
- 실시간 등록은 `LOGIN` 성공 후 `REG`, 해지는 `REMOVE` 순서로만 수행한다.
- 연속조회는 응답 헤더의 `cont-yn`, `next-key`를 다음 요청에 전달하는 것을 기본 규약으로 한다.

## 9. LLD 티켓 분할 가이드(모듈 기준)

- LLD-`UAG`: 화면/API 계약 및 검증 규칙
- LLD-`TSE`: 상태머신/전략 판정 상세 로직
- LLD-`OPM`: 주문/포지션 상태전이 및 틱 계산
- LLD-`KIA`: 키움 API 어댑터/오류 모델/재시도
- LLD-`CSM`: 설정/시크릿 저장소 및 검증
- LLD-`PRP`: 이벤트 저장/복구/리포트 집계

---
본 HLD는 SRS v0.1.0 기능/비기능 요구사항을 상위 설계 관점에서 모듈 경계와 계약 중심으로 구체화한 문서이다.
