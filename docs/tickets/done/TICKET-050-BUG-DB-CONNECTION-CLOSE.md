# TICKET-050-BUG-DB-CONNECTION-CLOSE

- 상태: todo
- 담당 에이전트: 버그 담당 에이전트
- 유형: 버그 리포트 및 디버깅
- 선행 티켓: TICKET-049-TEST-HLD-LLD-ILD
- 분류: 코드/구현
- 입력 산출물:
  - docs/tickets/reports/TICKET-049-TEST-REPORT.md
  - tests/test_uag.py
  - src/uag/*, src/prp/*
- 출력 산출물:
  - 버그 수정 코드
  - 회귀 테스트 결과
  - docs/tickets/reports/TICKET-050-BUGFIX-REPORT.md

## 증상
- 테스트 실행 시 SQLite 연결 미종료 ResourceWarning 발생.

## 작업 지시
- DB connection lifecycle을 명시적으로 관리하도록 수정한다.
- 테스트 종료 시 연결이 확실히 해제되는지 검증한다.
- 수정 후 `python -m pytest -q` 재실행하여 회귀 확인.
