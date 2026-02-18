# ILD KIA 테스트 케이스 문서 v0.1.0

## 목적
- KIA 배치 시세조회 계약(`fetch_quotes_batch`)과 토큰/재시도/오류 매핑 동작을 검증한다.

## 범위
- 시세 단건/배치 조회, 부분성공 응답, 401 갱신, 429/timeout 재시도 경계, 멱등 주문.

## 테스트 케이스 목록
| ID | 시나리오 | 사전조건 | 절차 | 기대결과 |
|---|---|---|---|---|
| ILD-KIA-TC-001 | 배치 시세 정상 조회 | symbols 2개, quote API 정상 | `fetch_quotes_batch` 호출 | `quotes=2`, `errors=0`, `partial=false` |
| ILD-KIA-TC-002 | 배치 시세 부분성공 | symbols 2개, 1개 timeout | `fetch_quotes_batch` 호출 | 성공 종목만 quotes 포함, `partial=true` |
| ILD-KIA-TC-003 | poll_cycle_id 전달 보존 | 고정 poll_cycle_id 입력 | 배치 호출 후 응답 확인 | 응답 `poll_cycle_id` 동일 |
| ILD-KIA-TC-004 | 401 강제 갱신 1회 재시도 | 첫 호출 401, 이후 성공 | `fetch_quote` 호출 | `force_refresh` 1회 후 성공 |
| ILD-KIA-TC-005 | 배치조회 retry 상한 | timeout/429 연속 발생 | `fetch_quotes_batch` 호출 | 최대 1회 재시도 후 종료 |
| ILD-KIA-TC-006 | 주문 timeout 재주문 금지 | submit timeout, 기존 주문 존재 | `submit_order` 재진입 | 중복조회 결과 반환, 재주문 없음 |
| ILD-KIA-TC-007 | 모드 전환 토큰 분리 | mock 토큰 보유 상태 | mode=live 요청 | mock 토큰 재사용 금지, live 토큰 신규 발급 |

## 수용 기준
- 배치조회에서 종목 단위 오류 코드가 유실되지 않아야 한다.
- `retryable` 플래그와 표준 오류 코드가 매핑 테이블과 일치해야 한다.
