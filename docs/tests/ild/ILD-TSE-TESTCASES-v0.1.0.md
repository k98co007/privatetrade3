# ILD TSE 테스트 케이스 문서 v0.1.0

## 목적
- TSE 전략 상태머신과 시세 지속 조회 루프(`RUNNING/DEGRADED/STOPPED`)를 재현 가능한 절차로 검증한다.

## 범위
- 기준가 캡처, 하락/반등 매수, 단일 매수 게이트, 수익보전 매도, 루프 장애 복구.

## 테스트 케이스 목록
| ID | 시나리오 | 사전조건 | 절차 | 기대결과 |
|---|---|---|---|---|
| ILD-TSE-TC-001 | 09:03 이전 무동작 | 감시종목 1개, 루프 RUNNING | 09:02:59 시세 입력 | 상태 전이/BUY 없음 |
| ILD-TSE-TC-002 | 기준가 1회 확정 | 09:03 이후 첫 시세 도착 | 동일 종목 시세 2회 입력 | 첫 틱만 `base_price` 저장 |
| ILD-TSE-TC-003 | -1% 하락 후 +0.2% 반등 매수 | 게이트 OPEN, 포지션 없음 | 하락→전저점 갱신→반등 입력 | `BUY_SIGNAL` 1회, 상태 `BUY_REQUESTED` |
| ILD-TSE-TC-004 | 다종목 동시 트리거 우선순위 | 감시종목 3개, 동일 시각 트리거 | sequence/watch_rank를 다르게 입력 | 시각→sequence→목록순으로 1건만 BUY |
| ILD-TSE-TC-005 | 연속 실패로 DEGRADED 전환 | 루프 RUNNING, 실패 임계치=3 | 배치조회 3사이클 연속 실패 모의 | `DEGRADED` 전환, 신규 BUY 차단 |
| ILD-TSE-TC-006 | DEGRADED 자동 복귀 | `DEGRADED`, 복구 임계치=2 | 배치조회 2사이클 연속 성공 모의 | `RUNNING` 복귀, BUY 재허용 |
| ILD-TSE-TC-007 | +1% 락 후 80% 보전율 매도 | LONG_OPEN, maxProfitRate>0 | profitRate 시퀀스 입력 | `MIN_PROFIT_LOCKED` 후 `SELL_SIGNAL` 1회 |
| ILD-TSE-TC-008 | 거래일 경계 초기화 | 전일 상태/게이트 존재 | trading_date 변경 이벤트 처리 | 종목/포트폴리오/루프 카운터 초기화 |

## 수용 기준
- 각 케이스는 동일 입력으로 2회 이상 동일 결과를 재현해야 한다.
- 로그에서 `poll_cycle_id`, 상태 전이, 차단 사유(`DEGRADED`)를 식별할 수 있어야 한다.
