# ILD OPM 테스트 환경 문서 v0.1.0

## 목적
- OPM 검증을 위한 실행 환경과 점검 절차를 표준화한다.

## 실행 환경
- OS: Windows 11
- Python: 3.11 이상
- 의존성: requirements.txt 기준 설치
- 실행 명령: python -m pytest tests/test_opm.py -q

## 연동 검증 파라미터
- `max_quote_staleness_ms=3000`
- 정합 워커 배치 크기: 기본 100
- 정합 재시도 백오프: 200/400/800ms

## 데이터/픽스처
- 주문/체결 정상 흐름 샘플(BUY->SELL)
- timeout 후 RECONCILING 흐름 샘플
- stale quote 샘플(`quote_as_of` 지연 초과)
- KIA fetchExecution/fetchPosition 불일치 보정 스텁
- TSE `DEGRADED` 상태 신호 스텁(신규 BUY 차단 상태)

## 환경 점검 체크리스트
- [ ] 가상환경 활성화 및 패키지 설치 완료
- [ ] 대상 테스트 단독 실행 성공
- [ ] stale 시세 주문 거부(`OPM_STALE_MARKET_PRICE`) 확인
- [ ] 예외 경로 결과 확인
- [ ] TSE `DEGRADED` 중 SELL/정합 지속 수행 확인
- [ ] 로그/리포트 저장 경로 확인
