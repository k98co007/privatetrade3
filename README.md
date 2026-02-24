# PrivateTrade3 MVP

키움 REST API 기반 알고리즘 트레이딩 시스템 MVP입니다.

## 실행 환경
- Python 3.11+

## 설치
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 테스트
```bash
python -m pytest -q
```

## 서버 실행
```bash
python src/app.py
```

## 로그
- 콘솔 로그와 함께 파일 로그가 저장됩니다.
- 경로: `runtime/logs/uag.log`
- 일자 롤링: 자정 기준으로 `runtime/logs/uag.log.YYYY-MM-DD` 파일이 생성되며 최근 30일 보관됩니다.

## CI/CD (MVP)
- GitHub Actions 워크플로우: `.github/workflows/python-ci.yml`
- 트리거: `push`, `pull_request`
- 실행 내용: Python 3.11 환경에서 의존성 설치 후 `pytest -q` 실행

## 로컬 배포(개인 PC)
- 1) 설치 섹션 절차 수행
- 2) 테스트: `python -m pytest -q`
- 3) 실행: `python src/app.py`

기본 접속:
- 웹 UI: http://127.0.0.1:8000/
- API 문서: http://127.0.0.1:8000/docs

## 주요 API
- `POST /api/settings`
- `POST /api/mode/switch`
- `POST /api/trading/start`
- `GET /api/monitor/status`
- `GET /api/reports/daily?date=YYYY-MM-DD`
- `GET /api/reports/trades?date=YYYY-MM-DD`

## 런타임/보안 파일
다음 경로는 Git 추적 제외됩니다.
- `runtime/config/*.local.json`
- `runtime/secrets/**`
- `runtime/state/**`
- `runtime/reports/**`
- `logs/**`

