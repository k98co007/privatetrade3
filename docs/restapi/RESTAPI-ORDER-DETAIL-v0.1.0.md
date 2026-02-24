# 키움 REST API 상세 - 주문 (TR별)

- 작성일: 2026-02-17
- 기준 가이드: https://openapi.kiwoom.com/guide/apiguide
- 카테고리: 국내주식 > 주문 (`jobTpCode=13`)
- 프로토콜/경로: `POST /api/dostk/ordr`

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
| `kt10000` | 주식 매수주문 |
| `kt10001` | 주식 매도주문 |
| `kt10002` | 주식 정정주문 |
| `kt10003` | 주식 취소주문 |
| `kt50000` | 금현물 매수주문 |
| `kt50001` | 금현물 매도주문 |
| `kt50002` | 금현물 정정주문 |
| `kt50003` | 금현물 취소주문 |

---

## 3. 대표 TR 상세 (`kt10000` 주식 매수주문)

### 3.1 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| `dmst_stex_tp` | Y | String | 국내거래소구분 (`KRX`, `NXT`, `SOR`) |
| `stk_cd` | Y | String | 종목코드 |
| `ord_qty` | Y | String | 주문수량 |
| `ord_uv` | N | String | 주문단가 |
| `trde_tp` | Y | String | 매매구분 (`0` 보통, `3` 시장가, `5` 조건부지정가, `61/62/81` 시간외, `10/13/16` IOC, `20/23/26` FOK 등) |
| `cond_uv` | N | String | 조건단가 |

### 3.2 요청 예시

```json
{
  "dmst_stex_tp": "SOR",
  "stk_cd": "005930",
  "ord_qty": "1",
  "ord_uv": "",
  "trde_tp": "3",
  "cond_uv": ""
}
```

### 3.3 응답 필드(요약)

| 필드 | 설명 |
| --- | --- |
| `ord_no` | 주문번호 |
| `dmst_stex_tp` | 국내거래소구분 |
| `return_code` | 결과코드 |
| `return_msg` | 결과메시지 |

---

## 4. Python 샘플 (주문)

```python
import requests
import json


def fn_kt10000(token, data, cont_yn='N', next_key=''):
    host = 'https://api.kiwoom.com'
    endpoint = '/api/dostk/ordr'
    url = host + endpoint

    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'cont-yn': cont_yn,
        'next-key': next_key,
        'api-id': 'kt10000',
    }

    response = requests.post(url, headers=headers, json=data)
    print('Code:', response.status_code)
    print('Header:', json.dumps({k: response.headers.get(k) for k in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
    print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))


if __name__ == '__main__':
    MY_ACCESS_TOKEN = '사용자 AccessToken'
    params = {
      'dmst_stex_tp': 'SOR',
        'stk_cd': '005930',
        'ord_qty': '1',
        'ord_uv': '',
        'trde_tp': '3',
        'cond_uv': ''
    }
    fn_kt10000(token=MY_ACCESS_TOKEN, data=params)
```

---

## 5. 구현 메모

- 동일 endpoint(`/api/dostk/ordr`)에서 `api-id`로 매수/매도/정정/취소 구분
- 주문 API는 네트워크 timeout 시 즉시 재주문보다 주문조회 기반 정합 우선
- 운영 시 `clientOrderId`/주문멱등 정책을 내부적으로 별도 유지 권장
