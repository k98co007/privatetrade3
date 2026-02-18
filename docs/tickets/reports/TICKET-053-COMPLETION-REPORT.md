# TICKET-053-DEV-UAG-TSE-PRP Completion Report

## 구현 범위
- 모니터링 화면 자동 갱신(주기 폴링) 적용
- 모니터링/리포트 API에 인터뷰 지정 컬럼 데이터(`monitoringRows`) 추가
- UI 모니터링/리포트 테이블에 다음 12개 컬럼 고정 반영
  - 종목명 | 종목코드 | 9시3분 가격 | 현재 가격 | 전저점 시간 | 전저점 가격 | 매수 시간 | 매수 가격 | 전고점 시간 | 전고점 가격 | 매도 시간 | 매도 가격
- UI 시간 필드 HH:MM:SS 포맷 보장
- 매수/매도 조건 충족 시 주문 전송 시도 로직 유지(거부/잔액부족은 시도 자체를 막지 않음)
- 리포트 `현재가격`은 장마감(15:30) 가격 우선 사용

## 핵심 변경 사항
- `src/uag/service.py`
  - 심볼별 런타임 모니터링 스냅샷 저장/갱신 로직 추가
  - `/api/monitor/status`, `/api/reports/daily`, `/api/reports/trades` 응답에 `monitoringRows` 포함
  - 리포트 생성 시 `currentPrice`를 `current_price_at_close(15:30 이후 최초 관측값)`로 우선 사용
- `src/tse/quote_monitoring.py`
  - `QuoteCycleResult`에 `quotes` 포함(스냅샷 갱신 원천 데이터 제공)
- `src/uag/bootstrap.py`
  - 모니터링 패널 수동 Refresh 버튼 의존 제거, 자동 폴링(`setInterval`) 추가
  - 모니터링/리포트 패널 모두 인터뷰 지정 12개 컬럼 테이블 렌더링 적용

## 테스트 보강
- `tests/test_uag.py`
  - UI 자동 갱신 스크립트/필수 컬럼 존재 검증
  - monitor/daily/trades 응답에 `monitoringRows` 포함 검증
  - 리포트 `현재가격`이 15:30 종가(`current_price_at_close`) 사용 검증
  - 주문 거부 시에도 제출 시도/이벤트 전이(`PENDING_SUBMIT -> SUBMITTED -> REJECTED`) 검증

## 가정/제약
- 종목명 데이터 소스가 별도로 없어 현재는 종목코드를 종목명으로 동일 표기
- 장마감 가격은 15:30 시각 이후 최초 수신 시세를 종가로 간주
- 현재 구현은 런타임(in-memory) 스냅샷 기반이며, 다른 날짜 조회 시 `monitoringRows`는 빈 목록 반환 가능
