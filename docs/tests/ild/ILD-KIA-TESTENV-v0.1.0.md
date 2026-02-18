# ILD KIA 테스트 환경 문서 v0.1.0

## 목적
- KIA 검증을 위한 실행 환경과 점검 절차를 표준화한다.

## 실행 환경
- OS: Windows 11
- Python: 3.11 이상
- 의존성: requirements.txt 기준 설치
- 실행 명령: python -m pytest tests/test_kia.py -q

## 루프 연동 검증 파라미터
- 배치 시세조회 timeout: 700ms
- 배치 시세조회 재시도 상한: 1회
- 토큰 선제 갱신 safety window: 300초

## 데이터/픽스처
- quote API 종목별 응답 스텁(성공/timeout/429 혼합)
- auth API 스텁(정상/401 후 refresh 성공)
- order API 스텁(timeout 후 중복조회 성공)
- mock/live 모드별 base_url fixture
- idempotency store in-memory fixture

## 환경 점검 체크리스트
- [ ] 가상환경 활성화 및 패키지 설치 완료
- [ ] 대상 테스트 단독 실행 성공
- [ ] `fetch_quotes_batch` 부분성공(`partial=true`) 확인
- [ ] 예외 경로 결과 확인
- [ ] 배치조회 retry 상한(1회) 확인
- [ ] 로그/리포트 저장 경로 확인
