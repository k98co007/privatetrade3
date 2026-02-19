# KIWOOM REST API 가이드 요약 (v0.1.0)

- 작성일: 2026-02-17
- 기준 페이지: https://openapi.kiwoom.com/guide/apiguide
- 목적: 키움증권 REST API 가이드의 핵심 구조와 인증/호출 시작점을 빠르게 파악하기 위한 내부 요약

---

## 1. 가이드 구조(메뉴 기준)

가이드 페이지에는 다음과 같은 대분류가 노출된다.

- OAuth 인증
  - 접근토큰발급
  - 접근토큰폐기
- 국내주식
   - 계좌, 주문, 시세, 차트, 조건검색, 종목정보, 업종 등

> 참고: 세부 TR/엔드포인트는 페이지 내 동적 렌더링 및 명세서 다운로드 항목을 통해 제공된다.

---

## 2. OAuth 인증(접근토큰 발급)

가이드에서 확인 가능한 `접근토큰 발급(au10001)`의 기본 정보는 아래와 같다.

| 항목 | 값 |
| --- | --- |
| Method | `POST` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` *(가이드 주석: KRX 관련 제한 문구 존재)* |
| URL | `/oauth2/token` |
| Format | `JSON` |
| Content-Type | `application/json;charset=UTF-8` |

### 2.1 요청 바디

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `grant_type` | String | Y | `client_credentials` 입력 |
| `appkey` | String | Y | 앱키 |
| `secretkey` | String | Y | 시크릿키 |

예시:

```json
{
  "grant_type": "client_credentials",
  "appkey": "<APPKEY>",
  "secretkey": "<SECRETKEY>"
}
```

### 2.2 응답 바디(예시 필드)

| 필드 | 설명 |
| --- | --- |
| `expires_dt` | 만료일시 |
| `token_type` | 토큰 타입 |
| `token` | 접근토큰 |
| `return_code` | 처리 코드 |
| `return_msg` | 처리 메시지 |

예시:

```json
{
  "expires_dt": "20241107083713",
  "token_type": "bearer",
  "token": "<ACCESS_TOKEN>",
  "return_code": 0,
  "return_msg": "정상적으로 처리되었습니다"
}
```

---

## 3. 운영/모의 환경 구분

- 운영 API Host: `https://api.kiwoom.com`
- 모의투자 API Host: `https://mockapi.kiwoom.com`
- 환경별 지원 범위/시장(KRX 등) 제약은 가이드 문구 및 최신 공식 명세서에서 최종 확인 필요

---

## 4. 실무 적용 체크포인트

1. **공식 명세서 다운로드본 우선 적용**
   - 엔드포인트, 요청/응답 필드, 오류코드, 호출 제한은 최신 다운로드 명세서 기준으로 확정
2. **토큰 수명/재발급 처리**
   - `expires_dt` 기반 만료 전 갱신 전략 적용
3. **환경 분리**
   - 운영/모의 Host 및 자격증명 분리 관리
4. **요청 제한 대응**
   - 레이트 리미터/큐/재시도 정책(특히 429 계열) 반영
5. **조회/주문 채널 단순화**
   - 조회/주문 중심 REST 흐름으로 설계

---

## 5. privateTrade3 연계 메모

현재 저장소의 `src/kia` 모듈(`api_client.py`, `gateway.py`, `token_provider.py`, `retry.py`) 구조는
공식 REST 스펙 반영에 필요한 추상화 계층을 이미 갖추고 있어, 아래 순서로 반영하는 것이 효율적이다.

1. 명세서 다운로드본 기준 엔드포인트/파라미터 확정
2. `endpoint_resolver.py`에 카테고리별 경로 매핑 보강
3. `error_mapper.py`에 공식 오류코드 매핑 보강
4. `tests/test_kia.py`에 운영/모의 분기 및 토큰/재시도 시나리오 추가

---

## 6. 출처

- 공식 포털: https://openapi.kiwoom.com/
- API 가이드: https://openapi.kiwoom.com/guide/apiguide
- 사내 조사 노트: `docs/research/KIWOOM-REST-API-RESEARCH-20260217.md`

---

## 7. 한계 및 주의

- 본 문서는 가이드 페이지에서 확인 가능한 항목 중심 요약이다.
- 세부 TR 스펙(필드 타입/길이/조건, 오류코드 상세, 호출 제한 수치)은 반드시 공식 명세서 다운로드본으로 재검증해야 한다.

---

## 8. 상세 문서

- 시세/주문 상세 + Python 샘플 정리:
   - `docs/restapi/RESTAPI-QUOTE-REALTIME-ORDER-v0.1.0.md`
- 카테고리별 분리 상세:
   - `docs/restapi/RESTAPI-QUOTE-DETAIL-v0.1.0.md`
   - `docs/restapi/RESTAPI-ORDER-DETAIL-v0.1.0.md`
- 카테고리별 ULTRA(초세분화):
   - `docs/restapi/RESTAPI-QUOTE-ULTRA-v0.1.0.md`
   - `docs/restapi/RESTAPI-ORDER-ULTRA-v0.1.0.md`

---

## 9. 국내주식 차트: 주식분봉차트조회요청 (`ka10080`)

- 확인일: 2026-02-19
- 출처: https://openapi.kiwoom.com/guide/apiguide (동적 로딩: `/guide/apiGuideList`, `/guide/apiGuideContents`)

### 9.1 기본 정보

| 항목 | 값 |
| --- | --- |
| API명 | 주식분봉차트조회요청 |
| API ID(TR명) | `ka10080` |
| Method | `POST` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` *(KRX만 지원가능 문구 표기)* |
| URL | `/api/dostk/chart` |
| Format | `JSON` |
| Content-Type | `application/json;charset=UTF-8` |

### 9.2 요청 Header

| Element | 필수 | 타입 | 길이 | 설명 |
| --- | --- | --- | --- | --- |
| `authorization` | Y | String | 1000 | `Bearer {ACCESS_TOKEN}` |
| `cont-yn` | N | String | 1 | 연속조회 시 이전 응답 Header의 `cont-yn` 값 사용 |
| `next-key` | N | String | 50 | 연속조회 시 이전 응답 Header의 `next-key` 값 사용 |
| `api-id` | Y | String | 10 | `ka10080` |

### 9.3 요청 Body

| Element | 필수 | 타입 | 길이 | 설명 |
| --- | --- | --- | --- | --- |
| `stk_cd` | Y | String | 20 | 종목코드 *(KRX:039490, NXT:039490_NX, SOR:039490_AL 형식 예시)* |
| `tic_scope` | Y | String | 2 | 분봉 단위: `1,3,5,10,15,30,45,60` |
| `upd_stkpc_tp` | Y | String | 1 | 수정주가구분 (`0` or `1`) |
| `base_dt` | N | String | 8 | 기준일자 `YYYYMMDD` |

요청 예시:

```json
{
   "stk_cd": "005930",
   "tic_scope": "1",
   "upd_stkpc_tp": "1",
   "base_dt": "20260202"
}
```

### 9.4 응답 Header

| Element | 타입 | 설명 |
| --- | --- | --- |
| `cont-yn` | String | 다음 데이터 존재 시 `Y` |
| `next-key` | String | 다음 데이터 존재 시 연속조회 키 |
| `api-id` | String | `ka10080` |

### 9.5 응답 Body

- 루트 필드
   - `stk_cd`: 종목코드
   - `stk_min_pole_chart_qry`: 분봉 데이터 배열
   - `return_code`, `return_msg`: 공통 처리 결과

- `stk_min_pole_chart_qry` 배열 원소 필드
   - `cur_prc` (현재가/종가)
   - `trde_qty` (거래량)
   - `cntr_tm` (체결시간)
   - `open_pric` (시가)
   - `high_pric` (고가)
   - `low_pric` (저가)
   - `pred_pre` (전일대비)
   - `pred_pre_sig` (전일대비기호: `1` 상한가, `2` 상승, `3` 보합, `4` 하한가, `5` 하락)

응답 예시:

```json
{
   "stk_cd": "005930",
   "stk_min_pole_chart_qry": [
      {
         "cur_prc": "-78800",
         "trde_qty": "7913",
         "cntr_tm": "20250917132000",
         "open_pric": "-78850",
         "high_pric": "-78900",
         "low_pric": "-78800",
         "acc_trde_qty": "14947571",
         "pred_pre": "-600",
         "pred_pre_sig": "5"
      }
   ],
   "return_code": 0,
   "return_msg": "정상적으로 처리되었습니다"
}
```

### 9.6 연속조회 처리 요약

1. 최초 호출: Header에 `cont-yn: N`, `next-key: ""`로 호출
2. 응답 Header의 `cont-yn`이 `Y`이면, 같은 조건으로 재호출
3. 재호출 시 Header에 직전 응답의 `cont-yn`, `next-key` 값을 그대로 전달
4. `cont-yn`이 `N`이 될 때까지 반복

### 9.7 구현 시 주의사항

- 문서 예시 값에서 가격 계열 필드가 음수 문자열로 내려오는 케이스가 있으므로, 부호 처리 규칙을 저장소 도메인 모델(`tse`/`opm`)과 맞춰 일관 처리해야 한다.
- 응답 테이블에는 없는 `acc_trde_qty`가 응답 예시에 포함되어 있으므로, 실제 운영 응답을 기준으로 파서 허용 필드를 유연하게 유지하는 것이 안전하다.
- `base_dt` 미지정 시 조회 기준(서버 현재/최근 데이터 기준)은 운영 응답으로 확인 후 테스트케이스에 고정한다.
