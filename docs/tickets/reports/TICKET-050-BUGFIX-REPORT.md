# TICKET-050 버그 수정 리포트

- 티켓: TICKET-050-BUG-DB-CONNECTION-CLOSE
- 분류: 코드/구현
- 수행일: 2026-02-17

## 1) 문제 요약
- 테스트 수행 시 SQLite 연결 미종료 `ResourceWarning` 발생.
- 재현 조건: 전체 테스트 실행 시 경고 다수 관찰.

## 2) 수정 내용
- `PrpRepository`에 명시적 종료 API 추가:
  - `close()`
  - context manager (`__enter__`, `__exit__`)
- `UagService`에서 PRP 접근 시 context manager 사용으로 연결 자동 해제.
- `tests/test_prp.py`, `tests/test_opm.py`, `tests/test_uag.py`에서 테스트 종료 시 클라이언트/저장소 연결 정리 보강.

## 3) 검증 결과
- `python -m pytest -q` => 23 passed
- `python -W error::ResourceWarning -m pytest -q` => 23 passed
- 결론: 경고가 오류로 승격된 환경에서도 재현되지 않아 누수 이슈 해소로 판단.

## 4) 영향도
- 기능 동작 변경 없음.
- 자원 정리 안정성 개선.
