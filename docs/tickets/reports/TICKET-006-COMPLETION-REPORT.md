# TICKET-006 COMPLETION REPORT

- 티켓 ID: TICKET-006
- 티켓명: LLD-KIA 작성
- 완료일: 2026-02-17
- 담당: LLD agent (KIA)
- 입력 문서:
  - `docs/hld/HLD-v0.1.0.md` (4.4, 5, 6, 8)
  - `docs/lld/LLD-CSM-v0.1.0.md`
  - `docs/srs/SRS-v0.1.0.md`
- 산출 문서:
  - `docs/lld/LLD-KIA-v0.1.0.md`

## 1) 수행 결과
- KIA 모듈 범위/책임을 HLD 4.4 기준으로 상세화 완료
- 키움 REST 엔드포인트를 인증/시세/주문/체결 그룹으로 추상화 완료
- Mock/Live 엔드포인트 라우팅 로직 및 모드 변경 반영 규칙 정의 완료
- 토큰 라이프사이클(발급/선제갱신/강제갱신/무효화) 및 동시성 제어 설계 완료
- 표준 오류 모델(`code`, `message`, `retryable`, `source`) 및 HTTP/네트워크 매핑 정의 완료
- 재시도/백오프 정책과 주문 멱등성(`clientOrderId`) 가이드 정의 완료
- OPM/TSE가 사용하는 인터페이스 계약(DTO) 정의 완료
- 시퀀스 다이어그램 및 핵심 의사코드 작성 완료
- HLD/SRS 추적성 매트릭스 작성 완료

## 2) 핵심 설계 결정

### 결정 1: KIA를 EndpointResolver 기반 어댑터로 고정
- 방식: `AuthEndpoint`, `QuoteEndpoint`, `OrderEndpoint`, `ExecutionEndpoint`로 논리 분리
- 근거: HLD 4.4의 API 캡슐화 요구를 내부 표준 계약으로 일관화
- 영향: OPM/TSE는 브로커 상세 스펙에 비의존

### 결정 2: 토큰은 선제 갱신 + 401 시 1회 강제 갱신
- 방식: `refreshAt = expiresAt - 300s`, `single-flight` 동시성 제어
- 근거: HLD 6의 장애 완화 및 안정성 요구
- 영향: 토큰 만료로 인한 간헐 실패 감소, 중복 갱신 방지

### 결정 3: 주문은 멱등키 기반 중복 방지
- 방식: `SubmitOrderRequest.clientOrderId` 필수, 타임아웃 시 재주문 전 중복조회
- 근거: HLD 6.2 멱등 키 기반 중복 방지 요구
- 영향: 네트워크 불확실성 환경에서 중복 주문 리스크 축소

## 3) 체크리스트
- [x] HLD 4.4 책임 항목 반영
- [x] HLD 5 모듈 계약/오류 모델 반영
- [x] HLD 6 장애/복구(재시도, 멱등성) 반영
- [x] HLD 8 Mock/Live 라우팅 반영
- [x] SRS FR-014 반영
- [x] SRS 6.1 외부 인터페이스 반영
- [x] SRS NFR-002/NFR-005 반영
- [x] 한국어 문서화

## 4) 리스크 및 후속 권고
- 리스크: 브로커 오류 코드 체계 변경 시 매핑 누락 가능
- 권고: `ErrorMapper` 매핑 테이블을 설정화하여 무중단 업데이트 가능하게 설계
- 권고: 주문 멱등 스토어의 보존기간(TTL)과 재시작 복원 전략을 구현 단계에서 확정
- 권고: 429/5xx 빈도 기반으로 백오프 파라미터(`baseMs`, `maxMs`) 운영 튜닝

## 5) 결론
TICKET-006 요구사항(LLD-KIA 문서 신규 작성 및 엔드포인트 추상화/모드 라우팅/토큰 관리/오류 표준화/재시도·멱등성/OPM·TSE 인터페이스/시퀀스·의사코드/추적성 포함)을 충족하여 완료 처리한다.
