# 키움 REST API 상세 - 시세 (TR별)

- 작성일: 2026-02-17
- 기준 가이드: https://openapi.kiwoom.com/guide/apiguide
- 카테고리: 국내주식 > 시세 (`jobTpCode=02`)
- 프로토콜/경로: `POST /api/dostk/mrkcond`

---

## 1. 공통 호출 규약

- 운영 도메인: `https://api.kiwoom.com`
- 모의 도메인: `https://mockapi.kiwoom.com` *(가이드 문구: KRX만 지원 가능)*
- Header
  - `authorization: Bearer {access_token}`
  - `api-id: <TR ID>`
  - `cont-yn: N|Y`
  - `next-key: <연속조회키>`

---

## 2. TR 목록

| TR ID | TR명 |
| --- | --- |
| `ka10004` | 주식호가요청 |
| `ka10005` | 주식일주월시분요청 |
| `ka10006` | 주식시분요청 |
| `ka10007` | 시세표성정보요청 |
| `ka10011` | 신주인수권전체시세요청 |
| `ka10044` | 일별기관매매종목요청 |
| `ka10045` | 종목별기관매매추이요청 |
| `ka10046` | 체결강도추이시간별요청 |
| `ka10047` | 체결강도추이일별요청 |
| `ka10063` | 장중투자자별매매요청 |
| `ka10066` | 장마감후투자자별매매요청 |
| `ka10078` | 증권사별종목매매동향요청 |
| `ka10086` | 일별주가요청 |
| `ka10087` | 시간외단일가요청 |
| `ka50010` | 금현물체결추이 |
| `ka50012` | 금현물일별추이 |
| `ka50087` | 금현물예상체결 |
| `ka50100` | 금현물 시세정보 |
| `ka50101` | 금현물 호가 |
| `ka90005` | 프로그램매매추이요청 시간대별 |
| `ka90006` | 프로그램매매차익잔고추이요청 |
| `ka90007` | 프로그램매매누적추이요청 |
| `ka90008` | 종목시간별프로그램매매추이요청 |
| `ka90010` | 프로그램매매추이요청 일자별 |
| `ka90013` | 종목일별프로그램매매추이요청 |

---

## 3. 대표 TR 상세 (`ka10004` 주식호가요청)

### 3.1 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| `stk_cd` | Y | String | 종목코드 (예: `KRX:039490`, `NXT:039490_NX`, `SOR:039490_AL`) |

### 3.2 요청 예시

```json
{
  "stk_cd": "005930"
}
```

### 3.3 응답 필드(요약)

가이드 기준 응답에는 호가 1~10차, 잔량, 직전대비, 시간외 잔량, 총잔량 등이 포함된다.

- 예: `sel_fpr_bid`, `buy_fpr_bid`, `tot_sel_req`, `tot_buy_req`, `bid_req_base_tm`
- 공통 결과 필드: `return_code`, `return_msg`

> 전체 필드셋은 매우 길어 가이드 원문 기준으로 관리하며, 실제 구현 시 필요 필드만 매핑 권장.

---

## 4. Python 샘플 (시세)

```python
import requests
import json


def fn_ka10004(token, data, cont_yn='N', next_key=''):
    host = 'https://api.kiwoom.com'
    endpoint = '/api/dostk/mrkcond'
    url = host + endpoint

    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'cont-yn': cont_yn,
        'next-key': next_key,
        'api-id': 'ka10004',
    }

    response = requests.post(url, headers=headers, json=data)
    print('Code:', response.status_code)
    print('Header:', json.dumps({k: response.headers.get(k) for k in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
    print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))


if __name__ == '__main__':
    MY_ACCESS_TOKEN = '사용자 AccessToken'
    params = {'stk_cd': '005930'}
    fn_ka10004(token=MY_ACCESS_TOKEN, data=params)
```

---

## 5. 구현 메모

- `api-id`만 바꿔도 동일 endpoint(`/api/dostk/mrkcond`)에서 다수 시세 TR 호출 가능
- 연속조회 응답(`cont-yn=Y`) 수신 시 `next-key` 재전달
- 실서비스에서는 필요한 응답 필드만 DTO로 최소 매핑
