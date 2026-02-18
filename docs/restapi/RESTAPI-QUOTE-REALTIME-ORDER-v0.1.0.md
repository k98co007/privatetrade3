# KIWOOM REST API 상세 정리: 시세/주문 (v0.1.0)

- 작성일: 2026-02-17
- 기준: https://openapi.kiwoom.com/guide/apiguide
- 수집 방식: 가이드 페이지의 동적 호출(`/guide/apiGuideContents`) 기반 섹션/TR 목록 및 샘플 코드 확인

---

## 분리 상세 문서

- 시세(TR별): `docs/restapi/RESTAPI-QUOTE-DETAIL-v0.1.0.md`
- 주문(TR별): `docs/restapi/RESTAPI-ORDER-DETAIL-v0.1.0.md`

## ULTRA 문서 (초세분화)

- 시세 ULTRA: `docs/restapi/RESTAPI-QUOTE-ULTRA-v0.1.0.md`
- 주문 ULTRA: `docs/restapi/RESTAPI-ORDER-ULTRA-v0.1.0.md`

---

## 1) 공통 호출 규약

### 1.1 REST(시세/주문)

- Method: `POST`
- Content-Type: `application/json;charset=UTF-8`
- 공통 Header
  - `authorization: Bearer {access_token}`
  - `cont-yn: N|Y` (연속조회)
  - `next-key: ...` (연속조회키)
  - `api-id: <TR ID>`

---

## 2) 시세 섹션 상세 (`jobTpCode=02`)

### 2.1 기본 정보

- 구분: 국내주식 > 시세
- Protocol: REST
- Host(운영): `https://api.kiwoom.com`
- Host(모의): `https://mockapi.kiwoom.com`
- URL: `/api/dostk/mrkcond`

### 2.2 TR 목록 (가이드 노출 전체)

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

### 2.3 가이드 예시(기본 TR: `ka10004`)

요청 Body 예시:

```json
{
  "stk_cd": "005930"
}
```

요청 Header 핵심:

- `api-id: ka10004`
- `authorization: Bearer {token}`

응답 예시에는 다수 시세 필드 + 공통 결과 필드가 포함됨:

- `return_code`
- `return_msg`

---

## 3) 주문 섹션 상세 (`jobTpCode=13`)

### 4.1 기본 정보

- 구분: 국내주식 > 주문
- Protocol: REST
- Host(운영): `https://api.kiwoom.com`
- Host(모의): `https://mockapi.kiwoom.com`
- URL: `/api/dostk/ordr`

### 4.2 TR 목록

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

### 4.3 가이드 예시(기본 TR: `kt10000`)

요청 Body 예시:

```json
{
  "dmst_stex_tp": "KRX",
  "stk_cd": "005930",
  "ord_qty": "1",
  "ord_uv": "",
  "trde_tp": "3",
  "cond_uv": ""
}
```

주요 필드(가이드 표기):

- `dmst_stex_tp`: 국내거래소구분 (`KRX`, `NXT`, `SOR`)
- `stk_cd`: 종목코드
- `ord_qty`: 주문수량
- `ord_uv`: 주문단가
- `trde_tp`: 매매구분 (예: `0` 보통, `3` 시장가, `5` 조건부지정가, `61/62/81` 시간외 등)
- `cond_uv`: 조건단가

응답 예시 필드:

- `ord_no`
- `return_code`
- `return_msg`

---

## 5) 가이드 Python 샘플 코드 정리

아래 코드는 가이드 페이지의 `Python` 탭 생성 로직을 기준으로 핵심 구조만 정리한 것이다.

### 5.1 REST 샘플 템플릿 (시세/주문 공통)

```python
import requests
import json

def fn_api(token, data, api_id, endpoint, cont_yn='N', next_key=''):
    host = 'https://api.kiwoom.com'
    url = host + endpoint

    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'cont-yn': cont_yn,
        'next-key': next_key,
        'api-id': api_id,
    }

    response = requests.post(url, headers=headers, json=data)

    print('Code:', response.status_code)
    print('Header:', json.dumps({
        key: response.headers.get(key)
        for key in ['next-key', 'cont-yn', 'api-id']
    }, indent=4, ensure_ascii=False))
    print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))

# 예시
# fn_api(token=MY_ACCESS_TOKEN, data={'stk_cd':'005930'}, api_id='ka10004', endpoint='/api/dostk/mrkcond')
# fn_api(token=MY_ACCESS_TOKEN, data={...}, api_id='kt10000', endpoint='/api/dostk/ordr')
```

### 5.2 실시간(WebSocket) 샘플 템플릿

```python
import asyncio
import json
import websockets

SOCKET_URL = 'wss://api.kiwoom.com:10000/api/dostk/websocket'
ACCESS_TOKEN = '사용자 AccessToken'

class WebSocketClient:
    def __init__(self, uri):
        self.uri = uri
        self.websocket = None
        self.connected = False
        self.keep_running = True

    async def connect(self):
        self.websocket = await websockets.connect(self.uri)
        self.connected = True
        await self.send_message({'trnm': 'LOGIN', 'token': ACCESS_TOKEN})

    async def send_message(self, message):
        if not self.connected:
            await self.connect()
        if not isinstance(message, str):
            message = json.dumps(message)
        await self.websocket.send(message)

    async def receive_messages(self):
        while self.keep_running:
            response = json.loads(await self.websocket.recv())
            print('실시간 시세 서버 응답 수신:', response)

async def main():
    ws = WebSocketClient(SOCKET_URL)
    await ws.connect()

    # 실시간 등록 예시 (00: 주문체결)
    await ws.send_message({
        'trnm': 'REG',
        'grp_no': '1',
        'refresh': '1',
        'data': [{'item': [''], 'type': ['00']}],
    })

    await ws.receive_messages()

# asyncio.run(main())
```

---

## 6) 구현 시 체크리스트 (privateTrade3 연계)

1. `api-id`를 엔드포인트와 함께 항상 명시 (`/mrkcond`, `/ordr`, `/websocket`)
2. 실시간은 `LOGIN` 후 `REG/REMOVE` 순서 강제
3. 주문(`kt10000~`)은 멱등키/중복조회 정책과 함께 사용
4. 연속조회 응답 시 `cont-yn`, `next-key` 헤더를 다음 요청에 전달
5. 운영/모의 도메인 및 토큰 분리

---

## 7) 출처

- 가이드 메인: https://openapi.kiwoom.com/guide/apiguide
- 동적 목록/상세 호출(가이드 페이지 내부 호출):
  - `/guide/apiGuideContents`
  - `/guide/apiGuideList`

> 참고: 가이드의 `getExampleParameter` 직접 호출은 환경에 따라 500이 발생할 수 있어, 본 문서의 샘플은 섹션 상세 HTML에 포함된 예제 파라미터/코드 생성 로직 기준으로 정리했다.
