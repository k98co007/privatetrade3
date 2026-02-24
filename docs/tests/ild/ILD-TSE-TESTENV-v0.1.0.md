# ILD TSE 테스트 환경 문서 v0.1.0

## 목적
- TSE 검증을 위한 실행 환경과 점검 절차를 표준화한다.

## 실행 환경
- OS: Windows 11
- Python: 3.11 이상
- 의존성: requirements.txt 기준 설치
- 실행 명령: python -m pytest tests/test_tse.py -q

## 루프 검증 파라미터
- `quotePollIntervalMs=1000`
- `quotePollTimeoutMs=700`
- `quoteConsecutiveErrorThreshold=3`
- `quoteRecoverySuccessThreshold=2`

## 데이터/픽스처
- 정상 시세 스트림 샘플(08:30 이전/이후 포함)
- 하락/반등 임계치 경계 샘플(-1.0%, +0.2%)
- 배치조회 실패 스텁(연속 timeout, 429, 부분성공)
- OPM/PRP 게이트웨이 목(명령 발행/저장 호출 검증)
- 고정 시계(FakeClock) + sequence generator 스텁

## 환경 점검 체크리스트
- [ ] 가상환경 활성화 및 패키지 설치 완료
- [ ] 대상 테스트 단독 실행 성공
- [ ] 루프 상태 전이(`RUNNING->DEGRADED->RUNNING`) 재현 성공
- [ ] 예외 경로 결과 확인
- [ ] `poll_cycle_id`/state 전이 로그 확인
- [ ] 로그/리포트 저장 경로 확인
