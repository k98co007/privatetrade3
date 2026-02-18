# KIWOOM REST API 조사 정리 (2026-02-17)

## 1) 목적

본 문서는 키움증권 API 연동 시 다음을 빠르게 판단할 수 있도록 정리한다.

- 공식 REST API 프로토콜(인증/호스트/카테고리) 확인
- 샘플/래퍼 라이브러리(파이썬 API 레벨) 후보 확인
- REST API와 기존 OpenAPI+ (OCX) 경로 구분

---

## 2) 조사 범위/방법

- 조사일: 2026-02-17
- 우선순위: 공식 사이트 > 공개 패키지(PyPI) > 공개 저장소(GitHub)
- 주의: 커뮤니티 라이브러리는 키움 공식 지원이 아님. 운영 전 모의 환경 검증 필요.

---

## 3) 공식 채널에서 확인된 내용

### 3.1 키움 REST 포털

- 포털: https://openapi.kiwoom.com/
- 가이드: https://openapi.kiwoom.com/guide/apiguide

가이드 페이지에서 확인된 핵심:

- `OAuth 인증` 섹션 존재
- `API 명세서 다운로드` 메뉴 존재
- 대분류로 `국내주식`, `주문`, `조건검색`, `차트`, `계좌` 등이 노출됨

### 3.2 인증 프로토콜 (공식 가이드 노출 기준)

`접근토큰 발급` 항목에서 확인된 정보:

- Method: `POST`
- 운영 도메인: `https://api.kiwoom.com`
- 모의투자 도메인: `https://mockapi.kiwoom.com` (가이드 문구에 KRX 지원 관련 주석 존재)
- URL: `/oauth2/token`
- Content-Type: `application/json;charset=UTF-8`
- 요청 바디 필드: `grant_type=client_credentials`, `appkey`, `secretkey`
- 응답 예시 필드: `expires_dt`, `token_type`, `token`, `return_code`, `return_msg`

참고: 위는 페이지 파싱으로 확보한 항목이며, 실제 상세 필드/제약은 포털 내 최신 명세서(PDF/문서 다운로드) 기준으로 재검증 필요.

---

## 4) REST vs OpenAPI+ (OCX) 구분

키움 메인 사이트의 Open API+ 소개 페이지에서 다음이 확인됨:

- OpenAPI+는 OCX 기반 개발 흐름(설치, KOA Studio, TR 조회/이벤트 기반)
- Windows/OCX 중심 설명
- REST 포털과 별도 채널

즉,

- REST API: HTTP/JSON + (실시간의 경우 별도 실시간 채널/소켓 계열)
- OpenAPI+: OCX/COM 이벤트 기반 (PyQt, QAxWidget 계열 래퍼가 주로 대상)

실무적으로 라이브러리 선택 시, 이름이 비슷해도 **REST 대상인지 OpenAPI+ 대상인지**를 반드시 먼저 확인해야 한다.

---

## 5) 파이썬 라이브러리/샘플 후보 (공개 소스 기반)

## 5.1 REST 계열 후보

### A. bamjun/kiwoom-rest-api

- GitHub: https://github.com/bamjun/kiwoom-rest-api
- PyPI: https://pypi.org/project/kiwoom-rest-api/
- 확인 내용:
  - `Kiwoom REST API client for Python`
  - 설치: `pip install kiwoom-rest-api`
  - 예시: 토큰 매니저 + `StockInfo` 호출
  - CLI 제공 (`kiwoom ...`)
  - WebSocket 사용 예시(실시간 타입 등록) 문서 포함
  - mock 도메인 지정 예시 포함

적합성 메모:

- REST 중심 프로젝트에 빠르게 PoC 하기 좋음
- 유지보수성은 릴리즈/이슈/커밋 활동 기준으로 추가 평가 필요

### B. breadum/kiwoom-restful

- GitHub: https://github.com/breadum/kiwoom-restful
- PyPI: https://pypi.org/project/kiwoom-restful/
- 문서: https://breadum.github.io/kiwoom-restful/0.2.7/
- 확인 내용:
  - REST 래퍼임을 명시
  - Async HTTP + WebSocket 처리 구조
  - 실시간 콜백/구독(register/remove) 예시 제공
  - 문서/README에 `비공식 프로젝트` 면책 문구 명시
  - 코드에서 요청 제한 정책 상수 확인:
    - 조회/주문 초당 5건 정책 주석
    - `REQ_LIMIT_PER_SECOND = 5`

적합성 메모:

- 비동기/실시간 처리 구조를 참고하기 좋음
- RC 단계 표기(안정성 검증 필요)

## 5.2 OpenAPI+ (OCX) 계열 후보 — REST 대체재 아님

### C. sharebook-kr/pykiwoom

- GitHub: https://github.com/sharebook-kr/pykiwoom
- PyPI: https://pypi.org/project/pykiwoom/
- 확인 내용: `Python Wrapper for Kiwoom Open API+`

### D. elbakramer/koapy

- GitHub: https://github.com/elbakramer/koapy
- Docs: https://koapy.readthedocs.io/en/latest/
- 확인 내용: OpenAPI+ (OCX/COM, Qt 기반) 추상화 및 gRPC 보조 구조

정리:

- `pykiwoom`, `koapy`는 주로 OpenAPI+ 경로다.
- 현재 프로젝트처럼 REST 경로를 전제로 하면 1순위 채택 대상이 아니다.

---

## 6) 샘플 코드 확보 포인트

REST 관점에서 바로 참고 가능한 샘플 유형:

1. 토큰 발급
   - `/oauth2/token` 호출
   - `appkey/secretkey` 관리
2. 시세 조회
   - 단건 종목(예: 005930) 기본정보 요청
3. 실시간 수신
   - WebSocket 연결/로그인/구독 타입 등록
   - 콜백 처리 + 재연결/해제
4. 제한 대응
   - 초당 호출 제한 대비 큐/레이트리미터
   - 429/재시도 정책

---

## 7) 이 저장소(privateTrade3) 기준 권고

1. **공식 우선**: 스펙 고정은 반드시 `openapi.kiwoom.com`의 최신 명세서 다운로드본으로 확정
2. **래퍼는 참고/가속용**: 커뮤니티 래퍼는 구현 패턴 참고 또는 PoC 용도로 사용
3. **추상화 유지**: 현재 `src/kia`의 Gateway/Client 추상화는 유지하고, 외부 래퍼 종속을 코어 도메인으로 전파하지 않기
4. **REST/OCX 분리 원칙**: OpenAPI+용 샘플(OCX 기반)은 별도 트랙으로 관리

---

## 8) 확인한 출처 목록

### 공식

- https://openapi.kiwoom.com/
- https://openapi.kiwoom.com/guide/apiguide
- https://www.kiwoom.com/h/customer/download/VOpenApiInfoView

### REST 커뮤니티/패키지

- https://github.com/bamjun/kiwoom-rest-api
- https://pypi.org/project/kiwoom-rest-api/
- https://github.com/breadum/kiwoom-restful
- https://pypi.org/project/kiwoom-restful/
- https://breadum.github.io/kiwoom-restful/0.2.7/

### OpenAPI+ 커뮤니티/패키지 (비교 목적)

- https://github.com/sharebook-kr/pykiwoom
- https://pypi.org/project/pykiwoom/
- https://github.com/elbakramer/koapy
- https://koapy.readthedocs.io/en/latest/

---

## 9) 후속 작업 제안

- 공식 포털의 API 명세서 다운로드본(PDF/CSV/json 등)을 팀 표준 템플릿으로 1회 정규화
  - 엔드포인트/필드/오류코드/요청 제한/실시간 타입을 표 형태로 내부 문서화
- `src/kia`와 공식 스펙 간 diff 체크리스트 생성
- Mock/Live 모두에 대해 토큰/요청제한/실시간 재연결 시나리오 테스트 케이스 추가
