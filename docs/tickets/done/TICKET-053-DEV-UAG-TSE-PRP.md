# TICKET-053-DEV-UAG-TSE-PRP

- 상태: todo
- 담당 에이전트: 실무 개발자
- 유형: 기능 개발
- 선행 티켓: TICKET-052-SRS-UPDATE
- 입력 산출물:
  - docs/srs/SRS-v0.2.0.md
  - docs/userinterview/20260218.md
- 출력 산출물:
  - src/uag/bootstrap.py
  - src/uag/service.py
  - src/tse/* (필요 시)
  - src/prp/* (필요 시)
  - tests/test_uag.py (및 관련 테스트)
  - docs/tickets/reports/TICKET-053-COMPLETION-REPORT.md
- 버전 정책: Minor 기능 개발 (v0.2.0)

## 작업 지시
고객 인터뷰의 신규 요구사항을 실제 코드로 반영한다.
- 모니터링 화면 자동 갱신
- 12개 컬럼 기반 모니터링 표시 및 시분초 포맷
- 매수/매도 조건 충족 시 주문 전송 로직 유지/보장
- 리포트에서 동일 항목 조회 가능
- 리포트 현재가격을 15:30 종가로 제공
- 관련 테스트 추가/갱신 후 `python -m pytest -q`로 검증
