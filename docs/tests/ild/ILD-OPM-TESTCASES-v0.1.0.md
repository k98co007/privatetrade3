# ILD OPM 테스트 케이스 문서 v0.1.0

## 목적
- OPM 주문/체결/정합 흐름과 시세 루프 저하 연동 안전 규칙을 검증한다.

## 범위
- 상태전이, 2틱 매도가, 멱등성, 정합 복구, stale 시세 거부, `DEGRADED` 상황 지속 처리.

## 테스트 케이스 목록
| ID | 시나리오 | 사전조건 | 절차 | 기대결과 |
|---|---|---|---|---|
| ILD-OPM-TC-001 | 매수 주문 정상 수락 | recovery_mode=false, FLAT | `place_buy_order` 호출 | `PENDING_SUBMIT->SUBMITTED->ACCEPTED` |
| ILD-OPM-TC-002 | 매도 2틱 계산 | currentPrice=71000 | `calc_sell_limit_price` 호출 | 결과 70800 |
| ILD-OPM-TC-003 | stale 시세 매도 거부 | `quote_as_of` 지연>3000ms | `guard_fresh_quote` 후 매도 요청 | `OPM_STALE_MARKET_PRICE` 반환 |
| ILD-OPM-TC-004 | 실행 멱등 처리 | 동일 `execution_id` 2회 입력 | `apply_execution_result` 호출 | 체결 1회만 반영 |
| ILD-OPM-TC-005 | submit timeout 정합 전환 | submit timeout 모의 | 주문 처리 실행 | 상태 `RECONCILING`, 재주문 없음 |
| ILD-OPM-TC-006 | 정합 불일치 보정 | internal/broker 수량 불일치 | `run_reconcile_once` 호출 | `fetch_position` 보정 수행 |
| ILD-OPM-TC-007 | TSE DEGRADED 중 지속 처리 | TSE는 신규 BUY 차단 상태 | 기존 LONG 포지션 SELL/정합 수행 | SELL/정합 워커 정상 동작 |

## 수용 기준
- 동일 입력 재실행 시 `state_version` 증가/체결 반영 결과가 일관되어야 한다.
- timeout/정합 경로에서 중복 주문이 발생하지 않아야 한다.
