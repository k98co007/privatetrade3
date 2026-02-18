# TICKET-009 COMPLETION REPORT

- 티켓 ID: TICKET-009
- 티켓명: LLD-UAG 작성
- 완료일: 2026-02-17
- 담당: LLD agent (UAG)
- 입력 문서:
  - `docs/hld/HLD-v0.1.0.md` (4.1, 5)
  - `docs/lld/LLD-CSM-v0.1.0.md`
  - `docs/lld/LLD-TSE-v0.1.0.md`
  - `docs/lld/LLD-PRP-v0.1.0.md`
  - `docs/srs/SRS-v0.1.0.md`
- 산출 문서:
  - `docs/lld/LLD-UAG-v0.1.0.md`

## 1) 수행 결과

- UAG 모듈 범위/책임을 HLD 4.1 및 모듈 계약(HLD 5) 기준으로 상세화 완료
- 브라우저 UI 연계 API 엔드포인트 정의 완료
  - 설정 조회/저장
  - 모드 전환
  - 투자 시작/중지
  - 모니터링 스냅샷/이벤트
  - 리포트 요약/상세 조회
- 요청/응답 스키마 및 필드 검증 규칙(종목/모드/자격정보/날짜) 명세 완료
- 자격정보 마스킹 동작 및 금지 규칙(로그/오류 상세 평문 차단) 정의 완료
- 모니터링 전송 전략(Polling + SSE, heartbeat/reconnect/fallback) 명세 완료
- 오류 응답 표준 포맷 및 HTTP 매핑 기준 정립 완료
- 로컬 운영 기준 인증/세션 가정(127.0.0.1 바인딩, 세션/CSRF, CORS 제한) 정리 완료
- FR/NFR 추적성 매트릭스 작성 완료

## 2) 핵심 설계 결정

### 결정 1: 응답 표준 포맷 단일화
- 방식: `success/requestId/data/meta` 또는 `success=false + error` 구조 강제
- 근거: HLD 5.1 공통 오류 모델 원칙, NFR-001 검증 가능성
- 영향: UI 예외처리 단순화, 모듈별 오류 일관 표출 가능

### 결정 2: 모니터링은 Polling 기본 + SSE 선택 혼합
- 방식: 기본 `GET /monitoring/snapshot`(2초), 가능 시 `GET /monitoring/events`(SSE)
- 근거: SRS FR-015의 실시간 또는 주기적 갱신 요구
- 영향: 네트워크/브라우저 제약 환경에서도 안정 동작, 고빈도 구간 지연 완화

### 결정 3: 로컬 사용 보안 최소기준 명문화
- 방식: loopback 바인딩, 세션 쿠키, 상태변경 API CSRF 필수
- 근거: SRS NFR-002, HLD 7.3 민감정보 보호 방향
- 영향: 개인 PC 단일 사용자 가정에서도 기본 공격면 축소

## 3) 체크리스트

- [x] HLD 4.1 UAG 책임 반영
- [x] HLD 5 모듈 간 계약 원칙 반영
- [x] 설정/모드전환/투자시작/모니터링/리포트 API 명세
- [x] 요청/응답 스키마 및 검증 규칙 명세
- [x] 자격정보 마스킹 정책 명세
- [x] Polling/SSE 전략 명세
- [x] 오류 응답 표준화 명세
- [x] 로컬 인증/세션 가정 명세
- [x] FR/NFR 추적성 매트릭스 작성
- [x] 한국어 문서화

## 4) 리스크 및 후속 권고

- 리스크: 장시간 SSE 연결 시 브라우저/네트워크 환경에 따라 이벤트 지연 또는 연결 빈번 재수립 가능
- 권고: UI에서 SSE 지연 감지 시 Polling 자동 폴백 상태를 명시 배지로 노출
- 권고: 상태변경 API에 대해 idempotency key 도입 검토(중복 클릭/재전송 대응)
- 권고: ILD 단계에서 CSM/TSE/PRP mock 기반 계약 테스트를 우선 작성

## 5) 결론

TICKET-009 요구사항(LLD-UAG 문서 신규 작성 및 엔드포인트/스키마·검증/마스킹/모니터링 전략/오류 표준/로컬 세션 가정/FR·NFR 추적성 포함)을 충족하여 완료 처리한다.
