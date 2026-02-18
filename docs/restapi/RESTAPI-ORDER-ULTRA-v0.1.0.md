# 키움 REST API ULTRA - 주문 (TR별 초세분화)

- 작성일: 2026-02-18
- 기준 가이드: https://openapi.kiwoom.com/guide/apiguide
- 범위: jobTpCode=13, endpoint=/api/dostk/ordr, protocol=REST
- 수준: TR별 요청/응답 필드 전체 전개 (초세분화)

## TR 인덱스

- kt10000: 주식 매수주문
- kt10001: 주식 매도주문
- kt10002: 주식 정정주문
- kt10003: 주식 취소주문
- kt50000: 금현물 매수주문
- kt50001: 금현물 매도주문
- kt50002: 금현물 정정주문
- kt50003: 금현물 취소주문

---

## TR 상세

### kt10000 - 주식 매수주문

- Endpoint: /api/dostk/ordr
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| dmst_stex_tp | Y | String | 국내거래소구분 KRX,NXT,SOR |
| stk_cd | Y | String | 종목코드 |
| ord_qty | Y | String | 주문수량 |
| ord_uv | N | String | 주문단가 |
| trde_tp | Y | String | 매매구분 0:보통 , 3:시장가 , 5:조건부지정가 , 81:장마감후시간외 , 61:장시작전시간외, 62:시간외단일가 , 6:최유리지정가 , 7:최우선지정가 , 10:보통(IOC) , 13:시장가(IOC) , 16:최유리(IOC) , 20:보통(FOK) , 23:시장가(FOK) , 26:최유리(FOK) , 28:스톱지정가,29:중간가,30:중간가(IOC),31:중간가(FOK) |
| cond_uv | N | String | 조건단가 |

#### 요청 예시

```json
{
	"dmst_stex_tp" : "KRX",
	"stk_cd" : "005930",
	"ord_qty" : "1",
	"ord_uv" : "",
	"trde_tp" : "3",
	"cond_uv" : ""
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| ord_no | N | String | 주문번호 |
| dmst_stex_tp | N | String | 국내거래소구분 |

### kt10001 - 주식 매도주문

- Endpoint: /api/dostk/ordr
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| dmst_stex_tp | Y | String | 국내거래소구분 KRX,NXT,SOR |
| stk_cd | Y | String | 종목코드 |
| ord_qty | Y | String | 주문수량 |
| ord_uv | N | String | 주문단가 |
| trde_tp | Y | String | 매매구분 0:보통 , 3:시장가 , 5:조건부지정가 , 81:장마감후시간외 , 61:장시작전시간외, 62:시간외단일가 , 6:최유리지정가 , 7:최우선지정가 , 10:보통(IOC) , 13:시장가(IOC) , 16:최유리(IOC) , 20:보통(FOK) , 23:시장가(FOK) , 26:최유리(FOK) , 28:스톱지정가,29:중간가,30:중간가(IOC),31:중간가(FOK) |
| cond_uv | N | String | 조건단가 |

#### 요청 예시

```json
{
	"dmst_stex_tp" : "KRX",
	"stk_cd" : "005930",
	"ord_qty" : "1",
	"ord_uv" : "",
	"trde_tp" : "3",
	"cond_uv" : ""
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| ord_no | N | String | 주문번호 |
| dmst_stex_tp | N | String | 국내거래소구분 |

### kt10002 - 주식 정정주문

- Endpoint: /api/dostk/ordr
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| dmst_stex_tp | Y | String | 국내거래소구분 KRX,NXT,SOR |
| orig_ord_no | Y | String | 원주문번호 |
| stk_cd | Y | String | 종목코드 |
| mdfy_qty | Y | String | 정정수량 |
| mdfy_uv | Y | String | 정정단가 |
| mdfy_cond_uv | N | String | 정정조건단가 |

#### 요청 예시

```json
{
	"dmst_stex_tp" : "KRX",
	"orig_ord_no" : "0000139",
	"stk_cd" : "005930",
	"mdfy_qty" : "1",
	"mdfy_uv" : "199700",
	"mdfy_cond_uv" : ""
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| ord_no | N | String | 주문번호 |
| base_orig_ord_no | N | String | 모주문번호 |
| mdfy_qty | N | String | 정정수량 |
| dmst_stex_tp | N | String | 국내거래소구분 |

### kt10003 - 주식 취소주문

- Endpoint: /api/dostk/ordr
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| dmst_stex_tp | Y | String | 국내거래소구분 KRX,NXT,SOR |
| orig_ord_no | Y | String | 원주문번호 |
| stk_cd | Y | String | 종목코드 |
| cncl_qty | Y | String | 취소수량 '0' 입력시 잔량 전부 취소 |

#### 요청 예시

```json
{
	"dmst_stex_tp" : "KRX",
	"orig_ord_no" : "0000140",
	"stk_cd" : "005930",
	"cncl_qty" : "1"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| ord_no | N | String | 주문번호 |
| base_orig_ord_no | N | String | 모주문번호 |
| cncl_qty | N | String | 취소수량 |

### kt50000 - 금현물 매수주문

- Endpoint: /api/dostk/ordr
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 M04020000 금 99.99_1kg, M04020100 미니금 99.99_100g |
| ord_qty | Y | String | 주문수량 |
| ord_uv | N | String | 주문단가 |
| trde_tp | Y | String | 매매구분 00:보통, 10:보통(IOC), 20:보통(FOK) |

#### 요청 예시

```json
{
	"stk_cd" : "M04020000",
	"ord_qty" : "1",
	"ord_uv" : "160000",
	"trde_tp" : "00"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| ord_no | N | String | 주문번호 |

### kt50001 - 금현물 매도주문

- Endpoint: /api/dostk/ordr
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 M04020000 금 99.99_1kg, M04020100 미니금 99.99_100g |
| ord_qty | Y | String | 주문수량 |
| ord_uv | N | String | 주문단가 |
| trde_tp | Y | String | 매매구분 00:보통, 10:보통(IOC), 20:보통(FOK) |

#### 요청 예시

```json
{
	"stk_cd" : "M04020000",
	"ord_qty" : "1",
	"ord_uv" : "160000",
	"trde_tp" : "00"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| ord_no | N | String | 주문번호 |

### kt50002 - 금현물 정정주문

- Endpoint: /api/dostk/ordr
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 M04020000 금 99.99_1kg, M04020100 미니금 99.99_100g |
| orig_ord_no | Y | String | 원주문번호 |
| mdfy_qty | Y | String | 정정수량 |
| mdfy_uv | Y | String | 정정단가 |

#### 요청 예시

```json
{
	"stk_cd" : "M04020000",
	"orig_ord_no" : "0000012",
	"mdfy_qty" : "1",
	"mdfy_uv" : "150000"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| ord_no | N | String | 주문번호 |
| base_orig_ord_no | N | String | 모주문번호 |
| mdfy_qty | N | String | 정정수량 |

### kt50003 - 금현물 취소주문

- Endpoint: /api/dostk/ordr
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| orig_ord_no | Y | String | 원주문번호 |
| stk_cd | Y | String | 종목코드 M04020000 금 99.99_1kg, M04020100 미니금 99.99_100g |
| cncl_qty | Y | String | 취소수량 '0' 입력시 잔량 전부 취소 |

#### 요청 예시

```json
{
	"orig_ord_no" : "0000014",
	"stk_cd" : "M04020000",
	"cncl_qty" : "1"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| ord_no | N | String | 주문번호 |
| base_orig_ord_no | N | String | 모주문번호 |
| cncl_qty | N | String | 취소수량 |


