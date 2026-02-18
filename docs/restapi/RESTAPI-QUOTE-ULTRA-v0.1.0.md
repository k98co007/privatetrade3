# 키움 REST API ULTRA - 시세 (TR별 초세분화)

- 작성일: 2026-02-18
- 기준 가이드: https://openapi.kiwoom.com/guide/apiguide
- 범위: jobTpCode=02, endpoint=/api/dostk/mrkcond, protocol=REST
- 수준: TR별 요청/응답 필드 전체 전개 (초세분화)

## TR 인덱스

- ka10004: 주식호가요청
- ka10005: 주식일주월시분요청
- ka10006: 주식시분요청
- ka10007: 시세표성정보요청
- ka10011: 신주인수권전체시세요청
- ka10044: 일별기관매매종목요청
- ka10045: 종목별기관매매추이요청
- ka10046: 체결강도추이시간별요청
- ka10047: 체결강도추이일별요청
- ka10063: 장중투자자별매매요청
- ka10066: 장마감후투자자별매매요청
- ka10078: 증권사별종목매매동향요청
- ka10086: 일별주가요청
- ka10087: 시간외단일가요청
- ka50010: 금현물체결추이
- ka50012: 금현물일별추이
- ka50087: 금현물예상체결
- ka50100: 금현물 시세정보
- ka50101: 금현물 호가
- ka90005: 프로그램매매추이요청 시간대별
- ka90006: 프로그램매매차익잔고추이요청
- ka90007: 프로그램매매누적추이요청
- ka90008: 종목시간별프로그램매매추이요청
- ka90010: 프로그램매매추이요청 일자별
- ka90013: 종목일별프로그램매매추이요청

---

## TR 상세

### ka10004 - 주식호가요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |

#### 요청 예시

```json
{
	"stk_cd" : "005930"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| bid_req_base_tm | N | String | 호가잔량기준시간 호가시간 |
| sel_10th_pre_req_pre | N | String | 매도10차선잔량대비 매도호가직전대비10 |
| sel_10th_pre_req | N | String | 매도10차선잔량 매도호가수량10 |
| sel_10th_pre_bid | N | String | 매도10차선호가 매도호가10 |
| sel_9th_pre_req_pre | N | String | 매도9차선잔량대비 매도호가직전대비9 |
| sel_9th_pre_req | N | String | 매도9차선잔량 매도호가수량9 |
| sel_9th_pre_bid | N | String | 매도9차선호가 매도호가9 |
| sel_8th_pre_req_pre | N | String | 매도8차선잔량대비 매도호가직전대비8 |
| sel_8th_pre_req | N | String | 매도8차선잔량 매도호가수량8 |
| sel_8th_pre_bid | N | String | 매도8차선호가 매도호가8 |
| sel_7th_pre_req_pre | N | String | 매도7차선잔량대비 매도호가직전대비7 |
| sel_7th_pre_req | N | String | 매도7차선잔량 매도호가수량7 |
| sel_7th_pre_bid | N | String | 매도7차선호가 매도호가7 |
| sel_6th_pre_req_pre | N | String | 매도6차선잔량대비 매도호가직전대비6 |
| sel_6th_pre_req | N | String | 매도6차선잔량 매도호가수량6 |
| sel_6th_pre_bid | N | String | 매도6차선호가 매도호가6 |
| sel_5th_pre_req_pre | N | String | 매도5차선잔량대비 매도호가직전대비5 |
| sel_5th_pre_req | N | String | 매도5차선잔량 매도호가수량5 |
| sel_5th_pre_bid | N | String | 매도5차선호가 매도호가5 |
| sel_4th_pre_req_pre | N | String | 매도4차선잔량대비 매도호가직전대비4 |
| sel_4th_pre_req | N | String | 매도4차선잔량 매도호가수량4 |
| sel_4th_pre_bid | N | String | 매도4차선호가 매도호가4 |
| sel_3th_pre_req_pre | N | String | 매도3차선잔량대비 매도호가직전대비3 |
| sel_3th_pre_req | N | String | 매도3차선잔량 매도호가수량3 |
| sel_3th_pre_bid | N | String | 매도3차선호가 매도호가3 |
| sel_2th_pre_req_pre | N | String | 매도2차선잔량대비 매도호가직전대비2 |
| sel_2th_pre_req | N | String | 매도2차선잔량 매도호가수량2 |
| sel_2th_pre_bid | N | String | 매도2차선호가 매도호가2 |
| sel_1th_pre_req_pre | N | String | 매도1차선잔량대비 매도호가직전대비1 |
| sel_fpr_req | N | String | 매도최우선잔량 매도호가수량1 |
| sel_fpr_bid | N | String | 매도최우선호가 매도호가1 |
| buy_fpr_bid | N | String | 매수최우선호가 매수호가1 |
| buy_fpr_req | N | String | 매수최우선잔량 매수호가수량1 |
| buy_1th_pre_req_pre | N | String | 매수1차선잔량대비 매수호가직전대비1 |
| buy_2th_pre_bid | N | String | 매수2차선호가 매수호가2 |
| buy_2th_pre_req | N | String | 매수2차선잔량 매수호가수량2 |
| buy_2th_pre_req_pre | N | String | 매수2차선잔량대비 매수호가직전대비2 |
| buy_3th_pre_bid | N | String | 매수3차선호가 매수호가3 |
| buy_3th_pre_req | N | String | 매수3차선잔량 매수호가수량3 |
| buy_3th_pre_req_pre | N | String | 매수3차선잔량대비 매수호가직전대비3 |
| buy_4th_pre_bid | N | String | 매수4차선호가 매수호가4 |
| buy_4th_pre_req | N | String | 매수4차선잔량 매수호가수량4 |
| buy_4th_pre_req_pre | N | String | 매수4차선잔량대비 매수호가직전대비4 |
| buy_5th_pre_bid | N | String | 매수5차선호가 매수호가5 |
| buy_5th_pre_req | N | String | 매수5차선잔량 매수호가수량5 |
| buy_5th_pre_req_pre | N | String | 매수5차선잔량대비 매수호가직전대비5 |
| buy_6th_pre_bid | N | String | 매수6차선호가 매수호가6 |
| buy_6th_pre_req | N | String | 매수6차선잔량 매수호가수량6 |
| buy_6th_pre_req_pre | N | String | 매수6차선잔량대비 매수호가직전대비6 |
| buy_7th_pre_bid | N | String | 매수7차선호가 매수호가7 |
| buy_7th_pre_req | N | String | 매수7차선잔량 매수호가수량7 |
| buy_7th_pre_req_pre | N | String | 매수7차선잔량대비 매수호가직전대비7 |
| buy_8th_pre_bid | N | String | 매수8차선호가 매수호가8 |
| buy_8th_pre_req | N | String | 매수8차선잔량 매수호가수량8 |
| buy_8th_pre_req_pre | N | String | 매수8차선잔량대비 매수호가직전대비8 |
| buy_9th_pre_bid | N | String | 매수9차선호가 매수호가9 |
| buy_9th_pre_req | N | String | 매수9차선잔량 매수호가수량9 |
| buy_9th_pre_req_pre | N | String | 매수9차선잔량대비 매수호가직전대비9 |
| buy_10th_pre_bid | N | String | 매수10차선호가 매수호가10 |
| buy_10th_pre_req | N | String | 매수10차선잔량 매수호가수량10 |
| buy_10th_pre_req_pre | N | String | 매수10차선잔량대비 매수호가직전대비10 |
| tot_sel_req_jub_pre | N | String | 총매도잔량직전대비 매도호가총잔량직전대비 |
| tot_sel_req | N | String | 총매도잔량 매도호가총잔량 |
| tot_buy_req | N | String | 총매수잔량 매수호가총잔량 |
| tot_buy_req_jub_pre | N | String | 총매수잔량직전대비 매수호가총잔량직전대비 |
| ovt_sel_req_pre | N | String | 시간외매도잔량대비 시간외 매도호가 총잔량 직전대비 |
| ovt_sel_req | N | String | 시간외매도잔량 시간외 매도호가 총잔량 |
| ovt_buy_req | N | String | 시간외매수잔량 시간외 매수호가 총잔량 |
| ovt_buy_req_pre | N | String | 시간외매수잔량대비 시간외 매수호가 총잔량 직전대비 |

### ka10005 - 주식일주월시분요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |

#### 요청 예시

```json
{
	"stk_cd" : "005930"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_ddwkmm | N | LIST | 주식일주월시분 |
| - date | N | String | 날짜 |
| - open_pric | N | String | 시가 |
| - high_pric | N | String | 고가 |
| - low_pric | N | String | 저가 |
| - close_pric | N | String | 종가 |
| - pre | N | String | 대비 |
| - flu_rt | N | String | 등락률 |
| - trde_qty | N | String | 거래량 |
| - trde_prica | N | String | 거래대금 |
| - for_poss | N | String | 외인보유 |
| - for_wght | N | String | 외인비중 |
| - for_netprps | N | String | 외인순매수 |
| - orgn_netprps | N | String | 기관순매수 |
| - ind_netprps | N | String | 개인순매수 |
| - crd_remn_rt | N | String | 신용잔고율 |
| - frgn | N | String | 외국계 |
| - prm | N | String | 프로그램 |

### ka10006 - 주식시분요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |

#### 요청 예시

```json
{
	"stk_cd" : "005930"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| date | N | String | 날짜 |
| open_pric | N | String | 시가 |
| high_pric | N | String | 고가 |
| low_pric | N | String | 저가 |
| close_pric | N | String | 종가 |
| pre | N | String | 대비 |
| flu_rt | N | String | 등락률 |
| trde_qty | N | String | 거래량 |
| trde_prica | N | String | 거래대금 |
| cntr_str | N | String | 체결강도 |

### ka10007 - 시세표성정보요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |

#### 요청 예시

```json
{
	"stk_cd" : "005930"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_nm | N | String | 종목명 |
| stk_cd | N | String | 종목코드 |
| date | N | String | 날짜 |
| tm | N | String | 시간 |
| pred_close_pric | N | String | 전일종가 |
| pred_trde_qty | N | String | 전일거래량 |
| upl_pric | N | String | 상한가 |
| lst_pric | N | String | 하한가 |
| pred_trde_prica | N | String | 전일거래대금 |
| flo_stkcnt | N | String | 상장주식수 |
| cur_prc | N | String | 현재가 |
| smbol | N | String | 부호 |
| flu_rt | N | String | 등락률 |
| pred_rt | N | String | 전일비 |
| open_pric | N | String | 시가 |
| high_pric | N | String | 고가 |
| low_pric | N | String | 저가 |
| cntr_qty | N | String | 체결량 |
| trde_qty | N | String | 거래량 |
| trde_prica | N | String | 거래대금 |
| exp_cntr_pric | N | String | 예상체결가 |
| exp_cntr_qty | N | String | 예상체결량 |
| exp_sel_pri_bid | N | String | 예상매도우선호가 |
| exp_buy_pri_bid | N | String | 예상매수우선호가 |
| trde_strt_dt | N | String | 거래시작일 |
| exec_pric | N | String | 행사가격 |
| hgst_pric | N | String | 최고가 |
| lwst_pric | N | String | 최저가 |
| hgst_pric_dt | N | String | 최고가일 |
| lwst_pric_dt | N | String | 최저가일 |
| sel_1bid | N | String | 매도1호가 |
| sel_2bid | N | String | 매도2호가 |
| sel_3bid | N | String | 매도3호가 |
| sel_4bid | N | String | 매도4호가 |
| sel_5bid | N | String | 매도5호가 |
| sel_6bid | N | String | 매도6호가 |
| sel_7bid | N | String | 매도7호가 |
| sel_8bid | N | String | 매도8호가 |
| sel_9bid | N | String | 매도9호가 |
| sel_10bid | N | String | 매도10호가 |
| buy_1bid | N | String | 매수1호가 |
| buy_2bid | N | String | 매수2호가 |
| buy_3bid | N | String | 매수3호가 |
| buy_4bid | N | String | 매수4호가 |
| buy_5bid | N | String | 매수5호가 |
| buy_6bid | N | String | 매수6호가 |
| buy_7bid | N | String | 매수7호가 |
| buy_8bid | N | String | 매수8호가 |
| buy_9bid | N | String | 매수9호가 |
| buy_10bid | N | String | 매수10호가 |
| sel_1bid_req | N | String | 매도1호가잔량 |
| sel_2bid_req | N | String | 매도2호가잔량 |
| sel_3bid_req | N | String | 매도3호가잔량 |
| sel_4bid_req | N | String | 매도4호가잔량 |
| sel_5bid_req | N | String | 매도5호가잔량 |
| sel_6bid_req | N | String | 매도6호가잔량 |
| sel_7bid_req | N | String | 매도7호가잔량 |
| sel_8bid_req | N | String | 매도8호가잔량 |
| sel_9bid_req | N | String | 매도9호가잔량 |
| sel_10bid_req | N | String | 매도10호가잔량 |
| buy_1bid_req | N | String | 매수1호가잔량 |
| buy_2bid_req | N | String | 매수2호가잔량 |
| buy_3bid_req | N | String | 매수3호가잔량 |
| buy_4bid_req | N | String | 매수4호가잔량 |
| buy_5bid_req | N | String | 매수5호가잔량 |
| buy_6bid_req | N | String | 매수6호가잔량 |
| buy_7bid_req | N | String | 매수7호가잔량 |
| buy_8bid_req | N | String | 매수8호가잔량 |
| buy_9bid_req | N | String | 매수9호가잔량 |
| buy_10bid_req | N | String | 매수10호가잔량 |
| sel_1bid_jub_pre | N | String | 매도1호가직전대비 |
| sel_2bid_jub_pre | N | String | 매도2호가직전대비 |
| sel_3bid_jub_pre | N | String | 매도3호가직전대비 |
| sel_4bid_jub_pre | N | String | 매도4호가직전대비 |
| sel_5bid_jub_pre | N | String | 매도5호가직전대비 |
| sel_6bid_jub_pre | N | String | 매도6호가직전대비 |
| sel_7bid_jub_pre | N | String | 매도7호가직전대비 |
| sel_8bid_jub_pre | N | String | 매도8호가직전대비 |
| sel_9bid_jub_pre | N | String | 매도9호가직전대비 |
| sel_10bid_jub_pre | N | String | 매도10호가직전대비 |
| buy_1bid_jub_pre | N | String | 매수1호가직전대비 |
| buy_2bid_jub_pre | N | String | 매수2호가직전대비 |
| buy_3bid_jub_pre | N | String | 매수3호가직전대비 |
| buy_4bid_jub_pre | N | String | 매수4호가직전대비 |
| buy_5bid_jub_pre | N | String | 매수5호가직전대비 |
| buy_6bid_jub_pre | N | String | 매수6호가직전대비 |
| buy_7bid_jub_pre | N | String | 매수7호가직전대비 |
| buy_8bid_jub_pre | N | String | 매수8호가직전대비 |
| buy_9bid_jub_pre | N | String | 매수9호가직전대비 |
| buy_10bid_jub_pre | N | String | 매수10호가직전대비 |
| sel_1bid_cnt | N | String | 매도1호가건수 |
| sel_2bid_cnt | N | String | 매도2호가건수 |
| sel_3bid_cnt | N | String | 매도3호가건수 |
| sel_4bid_cnt | N | String | 매도4호가건수 |
| sel_5bid_cnt | N | String | 매도5호가건수 |
| buy_1bid_cnt | N | String | 매수1호가건수 |
| buy_2bid_cnt | N | String | 매수2호가건수 |
| buy_3bid_cnt | N | String | 매수3호가건수 |
| buy_4bid_cnt | N | String | 매수4호가건수 |
| buy_5bid_cnt | N | String | 매수5호가건수 |
| lpsel_1bid_req | N | String | LP매도1호가잔량 |
| lpsel_2bid_req | N | String | LP매도2호가잔량 |
| lpsel_3bid_req | N | String | LP매도3호가잔량 |
| lpsel_4bid_req | N | String | LP매도4호가잔량 |
| lpsel_5bid_req | N | String | LP매도5호가잔량 |
| lpsel_6bid_req | N | String | LP매도6호가잔량 |
| lpsel_7bid_req | N | String | LP매도7호가잔량 |
| lpsel_8bid_req | N | String | LP매도8호가잔량 |
| lpsel_9bid_req | N | String | LP매도9호가잔량 |
| lpsel_10bid_req | N | String | LP매도10호가잔량 |
| lpbuy_1bid_req | N | String | LP매수1호가잔량 |
| lpbuy_2bid_req | N | String | LP매수2호가잔량 |
| lpbuy_3bid_req | N | String | LP매수3호가잔량 |
| lpbuy_4bid_req | N | String | LP매수4호가잔량 |
| lpbuy_5bid_req | N | String | LP매수5호가잔량 |
| lpbuy_6bid_req | N | String | LP매수6호가잔량 |
| lpbuy_7bid_req | N | String | LP매수7호가잔량 |
| lpbuy_8bid_req | N | String | LP매수8호가잔량 |
| lpbuy_9bid_req | N | String | LP매수9호가잔량 |
| lpbuy_10bid_req | N | String | LP매수10호가잔량 |
| tot_buy_req | N | String | 총매수잔량 |
| tot_sel_req | N | String | 총매도잔량 |
| tot_buy_cnt | N | String | 총매수건수 |
| tot_sel_cnt | N | String | 총매도건수 |

### ka10011 - 신주인수권전체시세요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| newstk_recvrht_tp | Y | String | 신주인수권구분 00:전체, 05:신주인수권증권, 07:신주인수권증서 |

#### 요청 예시

```json
{
	"newstk_recvrht_tp" : "00"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| newstk_recvrht_mrpr | N | LIST | 신주인수권시세 |
| - stk_cd | N | String | 종목코드 |
| - stk_nm | N | String | 종목명 |
| - cur_prc | N | String | 현재가 |
| - pred_pre_sig | N | String | 전일대비기호 |
| - pred_pre | N | String | 전일대비 |
| - flu_rt | N | String | 등락율 |
| - fpr_sel_bid | N | String | 최우선매도호가 |
| - fpr_buy_bid | N | String | 최우선매수호가 |
| - acc_trde_qty | N | String | 누적거래량 |
| - open_pric | N | String | 시가 |
| - high_pric | N | String | 고가 |
| - low_pric | N | String | 저가 |

### ka10044 - 일별기관매매종목요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| strt_dt | Y | String | 시작일자 YYYYMMDD |
| end_dt | Y | String | 종료일자 YYYYMMDD |
| trde_tp | Y | String | 매매구분 1:순매도, 2:순매수 |
| mrkt_tp | Y | String | 시장구분 001:코스피, 101:코스닥 |
| stex_tp | Y | String | 거래소구분 1:KRX, 2:NXT 3.통합 |

#### 요청 예시

```json
{
	"strt_dt" : "20241106",
	"end_dt" : "20241107",
	"trde_tp" : "1",
	"mrkt_tp" : "001",
	"stex_tp" : "3"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| daly_orgn_trde_stk | N | LIST | 일별기관매매종목 |
| - stk_cd | N | String | 종목코드 |
| - stk_nm | N | String | 종목명 |
| - netprps_qty | N | String | 순매수수량 |
| - netprps_amt | N | String | 순매수금액 |

### ka10045 - 종목별기관매매추이요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |
| strt_dt | Y | String | 시작일자 YYYYMMDD |
| end_dt | Y | String | 종료일자 YYYYMMDD |
| orgn_prsm_unp_tp | Y | String | 기관추정단가구분 1:매수단가, 2:매도단가 |
| for_prsm_unp_tp | Y | String | 외인추정단가구분 1:매수단가, 2:매도단가 |

#### 요청 예시

```json
{
	"stk_cd" : "005930",
	"strt_dt" : "20241007",
	"end_dt" : "20241107",
	"orgn_prsm_unp_tp" : "1",
	"for_prsm_unp_tp" : "1"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| orgn_prsm_avg_pric | N | String | 기관추정평균가 |
| for_prsm_avg_pric | N | String | 외인추정평균가 |
| stk_orgn_trde_trnsn | N | LIST | 종목별기관매매추이 |
| - dt | N | String | 일자 |
| - close_pric | N | String | 종가 |
| - pre_sig | N | String | 대비기호 |
| - pred_pre | N | String | 전일대비 |
| - flu_rt | N | String | 등락율 |
| - trde_qty | N | String | 거래량 |
| - orgn_dt_acc | N | String | 기관기간누적 |
| - orgn_daly_nettrde_qty | N | String | 기관일별순매매수량 |
| - for_dt_acc | N | String | 외인기간누적 |
| - for_daly_nettrde_qty | N | String | 외인일별순매매수량 |
| - limit_exh_rt | N | String | 한도소진율 |

### ka10046 - 체결강도추이시간별요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |

#### 요청 예시

```json
{
	"stk_cd" : "005930"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| cntr_str_tm | N | LIST | 체결강도시간별 |
| - cntr_tm | N | String | 체결시간 |
| - cur_prc | N | String | 현재가 |
| - pred_pre | N | String | 전일대비 |
| - pred_pre_sig | N | String | 전일대비기호 |
| - flu_rt | N | String | 등락율 |
| - trde_qty | N | String | 거래량 |
| - acc_trde_prica | N | String | 누적거래대금 |
| - acc_trde_qty | N | String | 누적거래량 |
| - cntr_str | N | String | 체결강도 |
| - cntr_str_5min | N | String | 체결강도5분 |
| - cntr_str_20min | N | String | 체결강도20분 |
| - cntr_str_60min | N | String | 체결강도60분 |
| - stex_tp | N | String | 거래소구분 |

### ka10047 - 체결강도추이일별요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |

#### 요청 예시

```json
{
	"stk_cd" : "005930"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| cntr_str_daly | N | LIST | 체결강도일별 |
| - dt | N | String | 일자 |
| - cur_prc | N | String | 현재가 |
| - pred_pre | N | String | 전일대비 |
| - pred_pre_sig | N | String | 전일대비기호 |
| - flu_rt | N | String | 등락율 |
| - trde_qty | N | String | 거래량 |
| - acc_trde_prica | N | String | 누적거래대금 |
| - acc_trde_qty | N | String | 누적거래량 |
| - cntr_str | N | String | 체결강도 |
| - cntr_str_5min | N | String | 체결강도5일 |
| - cntr_str_20min | N | String | 체결강도20일 |
| - cntr_str_60min | N | String | 체결강도60일 |

### ka10063 - 장중투자자별매매요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| mrkt_tp | Y | String | 시장구분 000:전체, 001:코스피, 101:코스닥 |
| amt_qty_tp | Y | String | 금액수량구분 1: 금액&수량 |
| invsr | Y | String | 투자자별 6:외국인, 7:기관계, 1:투신, 0:보험, 2:은행, 3:연기금, 4:국가, 5:기타법인 |
| frgn_all | Y | String | 외국계전체 1:체크, 0:미체크 |
| smtm_netprps_tp | Y | String | 동시순매수구분 1:체크, 0:미체크 |
| stex_tp | Y | String | 거래소구분 1:KRX, 2:NXT 3.통합 |

#### 요청 예시

```json
{
	"mrkt_tp" : "000",
	"amt_qty_tp" : "1",
	"invsr" : "6",
	"frgn_all" : "0",
	"smtm_netprps_tp" : "0",
	"stex_tp" : "3"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| opmr_invsr_trde | N | LIST | 장중투자자별매매 |
| - stk_cd | N | String | 종목코드 |
| - stk_nm | N | String | 종목명 |
| - cur_prc | N | String | 현재가 |
| - pre_sig | N | String | 대비기호 |
| - pred_pre | N | String | 전일대비 |
| - flu_rt | N | String | 등락율 |
| - acc_trde_qty | N | String | 누적거래량 |
| - netprps_amt | N | String | 순매수금액 |
| - prev_netprps_amt | N | String | 이전순매수금액 |
| - buy_amt | N | String | 매수금액 |
| - netprps_amt_irds | N | String | 순매수금액증감 |
| - buy_amt_irds | N | String | 매수금액증감 |
| - sell_amt | N | String | 매도금액 |
| - sell_amt_irds | N | String | 매도금액증감 |
| - netprps_qty | N | String | 순매수수량 |
| - prev_pot_netprps_qty | N | String | 이전시점순매수수량 |
| - netprps_irds | N | String | 순매수증감 |
| - buy_qty | N | String | 매수수량 |
| - buy_qty_irds | N | String | 매수수량증감 |
| - sell_qty | N | String | 매도수량 |
| - sell_qty_irds | N | String | 매도수량증감 |

### ka10066 - 장마감후투자자별매매요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| mrkt_tp | Y | String | 시장구분 000:전체, 001:코스피, 101:코스닥 |
| amt_qty_tp | Y | String | 금액수량구분 1:금액, 2:수량 |
| trde_tp | Y | String | 매매구분 0:순매수, 1:매수, 2:매도 |
| stex_tp | Y | String | 거래소구분 1:KRX, 2:NXT 3.통합 |

#### 요청 예시

```json
{
	"mrkt_tp" : "000",
	"amt_qty_tp" : "1",
	"trde_tp" : "0",
	"stex_tp" : "3"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| opaf_invsr_trde | N | LIST | 장중투자자별매매차트 |
| - stk_cd | N | String | 종목코드 |
| - stk_nm | N | String | 종목명 |
| - cur_prc | N | String | 현재가 |
| - pre_sig | N | String | 대비기호 |
| - pred_pre | N | String | 전일대비 |
| - flu_rt | N | String | 등락률 |
| - trde_qty | N | String | 거래량 |
| - ind_invsr | N | String | 개인투자자 |
| - frgnr_invsr | N | String | 외국인투자자 |
| - orgn | N | String | 기관계 |
| - fnnc_invt | N | String | 금융투자 |
| - insrnc | N | String | 보험 |
| - invtrt | N | String | 투신 |
| - etc_fnnc | N | String | 기타금융 |
| - bank | N | String | 은행 |
| - penfnd_etc | N | String | 연기금등 |
| - samo_fund | N | String | 사모펀드 |
| - natn | N | String | 국가 |
| - etc_corp | N | String | 기타법인 |

### ka10078 - 증권사별종목매매동향요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| mmcm_cd | Y | String | 회원사코드 회원사 코드는 ka10102 조회 |
| stk_cd | Y | String | 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |
| strt_dt | Y | String | 시작일자 YYYYMMDD |
| end_dt | Y | String | 종료일자 YYYYMMDD |

#### 요청 예시

```json
{
	"mmcm_cd" : "001",
	"stk_cd" : "005930",
	"strt_dt" : "20241106",
	"end_dt" : "20241107"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| sec_stk_trde_trend | N | LIST | 증권사별종목매매동향 |
| - dt | N | String | 일자 |
| - cur_prc | N | String | 현재가 |
| - pre_sig | N | String | 대비기호 |
| - pred_pre | N | String | 전일대비 |
| - flu_rt | N | String | 등락율 |
| - acc_trde_qty | N | String | 누적거래량 |
| - netprps_qty | N | String | 순매수수량 |
| - buy_qty | N | String | 매수수량 |
| - sell_qty | N | String | 매도수량 |

### ka10086 - 일별주가요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |
| qry_dt | Y | String | 조회일자 YYYYMMDD |
| indc_tp | Y | String | 표시구분 0:수량, 1:금액(백만원) |

#### 요청 예시

```json
{
	"stk_cd" : "005930",
	"qry_dt" : "20241125",
	"indc_tp" : "0"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| daly_stkpc | N | LIST | 일별주가 |
| - date | N | String | 날짜 |
| - open_pric | N | String | 시가 |
| - high_pric | N | String | 고가 |
| - low_pric | N | String | 저가 |
| - close_pric | N | String | 종가 |
| - pred_rt | N | String | 전일비 |
| - flu_rt | N | String | 등락률 |
| - trde_qty | N | String | 거래량 |
| - amt_mn | N | String | 금액(백만) |
| - crd_rt | N | String | 신용비 |
| - ind | N | String | 개인 |
| - orgn | N | String | 기관 |
| - for_qty | N | String | 외인수량 |
| - frgn | N | String | 외국계 |
| - prm | N | String | 프로그램 |
| - for_rt | N | String | 외인비 |
| - for_poss | N | String | 외인보유 |
| - for_wght | N | String | 외인비중 |
| - for_netprps | N | String | 외인순매수 |
| - orgn_netprps | N | String | 기관순매수 |
| - ind_netprps | N | String | 개인순매수 |
| - crd_remn_rt | N | String | 신용잔고율 |

### ka10087 - 시간외단일가요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 |

#### 요청 예시

```json
{
	"stk_cd" : "005930"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| bid_req_base_tm | N | String | 호가잔량기준시간 |
| ovt_sigpric_sel_bid_jub_pre_5 | N | String | 시간외단일가_매도호가직전대비5 |
| ovt_sigpric_sel_bid_jub_pre_4 | N | String | 시간외단일가_매도호가직전대비4 |
| ovt_sigpric_sel_bid_jub_pre_3 | N | String | 시간외단일가_매도호가직전대비3 |
| ovt_sigpric_sel_bid_jub_pre_2 | N | String | 시간외단일가_매도호가직전대비2 |
| ovt_sigpric_sel_bid_jub_pre_1 | N | String | 시간외단일가_매도호가직전대비1 |
| ovt_sigpric_sel_bid_qty_5 | N | String | 시간외단일가_매도호가수량5 |
| ovt_sigpric_sel_bid_qty_4 | N | String | 시간외단일가_매도호가수량4 |
| ovt_sigpric_sel_bid_qty_3 | N | String | 시간외단일가_매도호가수량3 |
| ovt_sigpric_sel_bid_qty_2 | N | String | 시간외단일가_매도호가수량2 |
| ovt_sigpric_sel_bid_qty_1 | N | String | 시간외단일가_매도호가수량1 |
| ovt_sigpric_sel_bid_5 | N | String | 시간외단일가_매도호가5 |
| ovt_sigpric_sel_bid_4 | N | String | 시간외단일가_매도호가4 |
| ovt_sigpric_sel_bid_3 | N | String | 시간외단일가_매도호가3 |
| ovt_sigpric_sel_bid_2 | N | String | 시간외단일가_매도호가2 |
| ovt_sigpric_sel_bid_1 | N | String | 시간외단일가_매도호가1 |
| ovt_sigpric_buy_bid_1 | N | String | 시간외단일가_매수호가1 |
| ovt_sigpric_buy_bid_2 | N | String | 시간외단일가_매수호가2 |
| ovt_sigpric_buy_bid_3 | N | String | 시간외단일가_매수호가3 |
| ovt_sigpric_buy_bid_4 | N | String | 시간외단일가_매수호가4 |
| ovt_sigpric_buy_bid_5 | N | String | 시간외단일가_매수호가5 |
| ovt_sigpric_buy_bid_qty_1 | N | String | 시간외단일가_매수호가수량1 |
| ovt_sigpric_buy_bid_qty_2 | N | String | 시간외단일가_매수호가수량2 |
| ovt_sigpric_buy_bid_qty_3 | N | String | 시간외단일가_매수호가수량3 |
| ovt_sigpric_buy_bid_qty_4 | N | String | 시간외단일가_매수호가수량4 |
| ovt_sigpric_buy_bid_qty_5 | N | String | 시간외단일가_매수호가수량5 |
| ovt_sigpric_buy_bid_jub_pre_1 | N | String | 시간외단일가_매수호가직전대비1 |
| ovt_sigpric_buy_bid_jub_pre_2 | N | String | 시간외단일가_매수호가직전대비2 |
| ovt_sigpric_buy_bid_jub_pre_3 | N | String | 시간외단일가_매수호가직전대비3 |
| ovt_sigpric_buy_bid_jub_pre_4 | N | String | 시간외단일가_매수호가직전대비4 |
| ovt_sigpric_buy_bid_jub_pre_5 | N | String | 시간외단일가_매수호가직전대비5 |
| ovt_sigpric_sel_bid_tot_req | N | String | 시간외단일가_매도호가총잔량 |
| ovt_sigpric_buy_bid_tot_req | N | String | 시간외단일가_매수호가총잔량 |
| sel_bid_tot_req_jub_pre | N | String | 매도호가총잔량직전대비 |
| sel_bid_tot_req | N | String | 매도호가총잔량 |
| buy_bid_tot_req | N | String | 매수호가총잔량 |
| buy_bid_tot_req_jub_pre | N | String | 매수호가총잔량직전대비 |
| ovt_sel_bid_tot_req_jub_pre | N | String | 시간외매도호가총잔량직전대비 |
| ovt_sel_bid_tot_req | N | String | 시간외매도호가총잔량 |
| ovt_buy_bid_tot_req | N | String | 시간외매수호가총잔량 |
| ovt_buy_bid_tot_req_jub_pre | N | String | 시간외매수호가총잔량직전대비 |
| ovt_sigpric_cur_prc | N | String | 시간외단일가_현재가 |
| ovt_sigpric_pred_pre_sig | N | String | 시간외단일가_전일대비기호 |
| ovt_sigpric_pred_pre | N | String | 시간외단일가_전일대비 |
| ovt_sigpric_flu_rt | N | String | 시간외단일가_등락률 |
| ovt_sigpric_acc_trde_qty | N | String | 시간외단일가_누적거래량 |

### ka50010 - 금현물체결추이

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 M04020000 금 99.99_1kg, M04020100 미니금 99.99_100g |

#### 요청 예시

```json
{
	"stk_cd" : "M04020000"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| gold_cntr | N | LIST | 금현물체결추이 |
| - cntr_pric | N | String | 체결가 |
| - pred_pre | N | String | 전일 대비 |
| - flu_rt | N | String | 등락율 |
| - trde_qty | N | String | 누적 거래량 |
| - acc_trde_prica | N | String | 누적 거래대금 |
| - cntr_trde_qty | N | String | 거래량(체결량) |
| - tm | N | String | 체결시간 |
| - pre_sig | N | String | 전일대비기호 |
| - pri_sel_bid_unit | N | String | 매도호가 |
| - pri_buy_bid_unit | N | String | 매수호가 |
| - trde_pre | N | String | 전일 거래량 대비 비율 |
| - trde_tern_rt | N | String | 전일 거래량 대비 순간 거래량 비율 |
| - cntr_str | N | String | 체결강도 |

### ka50012 - 금현물일별추이

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 M04020000 금 99.99_1kg, M04020100 미니금 99.99_100g |
| base_dt | Y | String | 기준일자 YYYYMMDD |

#### 요청 예시

```json
{
	"stk_cd" : "M04020000",
	"base_dt" : "20250820"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| gold_daly_trnsn | N | LIST | 금현물일별추이 |
| - cur_prc | N | String | 종가 |
| - pred_pre | N | String | 전일 대비 |
| - flu_rt | N | String | 등락율 |
| - trde_qty | N | String | 누적 거래량 |
| - acc_trde_prica | N | String | 누적 거래대금(백만) |
| - open_pric | N | String | 시가 |
| - high_pric | N | String | 고가 |
| - low_pric | N | String | 저가 |
| - dt | N | String | 일자 |
| - pre_sig | N | String | 전일대비기호 |
| - orgn_netprps | N | String | 기관 순매수 수량 |
| - for_netprps | N | String | 외국인 순매수 수량 |
| - ind_netprps | N | String | 순매매량(개인) |

### ka50087 - 금현물예상체결

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 M04020000 금 99.99_1kg, M04020100 미니금 99.99_100g |

#### 요청 예시

```json
{
	"stk_cd" : "M04020000"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| gold_expt_exec | N | LIST | 금현물예상체결 |
| - exp_cntr_pric | N | String | 예상 체결가 |
| - exp_pred_pre | N | String | 예상 체결가 전일대비 |
| - exp_flu_rt | N | String | 예상 체결가 등락율 |
| - exp_acc_trde_qty | N | String | 예상 체결 수량(누적) |
| - exp_cntr_trde_qty | N | String | 예상 체결 수량 |
| - exp_tm | N | String | 예상 체결 시간 |
| - exp_pre_sig | N | String | 예상 체결가 전일대비기호 |
| - stex_tp | N | String | 거래소 구분 |

### ka50100 - 금현물 시세정보

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 |

#### 요청 예시

```json
{
	"stk_cd" : "M04020000"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| pred_pre_sig | N | String | 전일대비기호 |
| pred_pre | N | String | 전일대비 |
| flu_rt | N | String | 등락율 |
| trde_qty | N | String | 거래량 |
| open_pric | N | String | 시가 |
| high_pric | N | String | 고가 |
| low_pric | N | String | 저가 |
| pred_rt | N | String | 전일비 |
| upl_pric | N | String | 상한가 |
| lst_pric | N | String | 하한가 |
| pred_close_pric | N | String | 전일종가 |

### ka50101 - 금현물 호가

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_cd | Y | String | 종목코드 M04020000 금 99.99_1kg, M04020100 미니금 99.99_100g |
| tic_scope | Y | String | 틱범위 1:1틱, 3:3틱, 5:5틱, 10:10틱, 30:30틱 |

#### 요청 예시

```json
{
	"stk_cd" : "M04020000",
	"tic_scope" : "1"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| gold_bid | N | LIST | 금현물호가 |
| - cntr_pric | N | String | 체결가 |
| - pred_pre | N | String | 전일 대비(원) |
| - flu_rt | N | String | 등락율 |
| - trde_qty | N | String | 누적 거래량 |
| - acc_trde_prica | N | String | 누적 거래대금 |
| - cntr_trde_qty | N | String | 거래량(체결량) |
| - tm | N | String | 체결시간 |
| - pre_sig | N | String | 전일대비기호 |
| - pri_sel_bid_unit | N | String | 매도호가 |
| - pri_buy_bid_unit | N | String | 매수호가 |
| - trde_pre | N | String | 전일 거래량 대비 비율 |
| - trde_tern_rt | N | String | 전일 거래량 대비 순간 거래량 비율 |
| - cntr_str | N | String | 체결강도 |
| - lpmmcm_nm_1 | N | String | K.O 접근도 |
| - stex_tp | N | String | 거래소구분 |

### ka90005 - 프로그램매매추이요청 시간대별

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| date | Y | String | 날짜 YYYYMMDD |
| amt_qty_tp | Y | String | 금액수량구분 1:금액(백만원), 2:수량(천주) |
| mrkt_tp | Y | String | 시장구분 코스피- 거래소구분값 1일경우:P00101, 2일경우:P001_NX01, 3일경우:P001_AL01  코스닥- 거래소구분값 1일경우:P10102, 2일경우:P101_NX02, 3일경우:P101_AL02 |
| min_tic_tp | Y | String | 분틱구분 0:틱, 1:분 |
| stex_tp | Y | String | 거래소구분 1:KRX, 2:NXT 3.통합 |

#### 요청 예시

```json
{
	"date" : "20241101",
	"amt_qty_tp" : "1",
	"mrkt_tp" : "P00101",
	"min_tic_tp" : "1",
	"stex_tp" : "1"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| prm_trde_trnsn | N | LIST | 프로그램매매추이 |
| - cntr_tm | N | String | 체결시간 |
| - dfrt_trde_sel | N | String | 차익거래매도 |
| - dfrt_trde_buy | N | String | 차익거래매수 |
| - dfrt_trde_netprps | N | String | 차익거래순매수 |
| - ndiffpro_trde_sel | N | String | 비차익거래매도 |
| - ndiffpro_trde_buy | N | String | 비차익거래매수 |
| - ndiffpro_trde_netprps | N | String | 비차익거래순매수 |
| - dfrt_trde_sell_qty | N | String | 차익거래매도수량 |
| - dfrt_trde_buy_qty | N | String | 차익거래매수수량 |
| - dfrt_trde_netprps_qty | N | String | 차익거래순매수수량 |
| - ndiffpro_trde_sell_qty | N | String | 비차익거래매도수량 |
| - ndiffpro_trde_buy_qty | N | String | 비차익거래매수수량 |
| - ndiffpro_trde_netprps_qty | N | String | 비차익거래순매수수량 |
| - all_sel | N | String | 전체매도 |
| - all_buy | N | String | 전체매수 |
| - all_netprps | N | String | 전체순매수 |
| - kospi200 | N | String | KOSPI200 |
| - basis | N | String | BASIS |

### ka90006 - 프로그램매매차익잔고추이요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| date | Y | String | 날짜 YYYYMMDD |
| stex_tp | Y | String | 거래소구분 1:KRX, 2:NXT 3.통합 |

#### 요청 예시

```json
{
	"date" : "20241125",
	"stex_tp" : "1"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| prm_trde_dfrt_remn_trnsn | N | LIST | 프로그램매매차익잔고추이 |
| - dt | N | String | 일자 |
| - buy_dfrt_trde_qty | N | String | 매수차익거래수량 |
| - buy_dfrt_trde_amt | N | String | 매수차익거래금액 |
| - buy_dfrt_trde_irds_amt | N | String | 매수차익거래증감액 |
| - sel_dfrt_trde_qty | N | String | 매도차익거래수량 |
| - sel_dfrt_trde_amt | N | String | 매도차익거래금액 |
| - sel_dfrt_trde_irds_amt | N | String | 매도차익거래증감액 |

### ka90007 - 프로그램매매누적추이요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| date | Y | String | 날짜 YYYYMMDD (종료일기준 1년간 데이터만 조회가능) |
| amt_qty_tp | Y | String | 금액수량구분 1:금액, 2:수량 |
| mrkt_tp | Y | String | 시장구분 0:코스피 , 1:코스닥 |
| stex_tp | Y | String | 거래소구분 1:KRX, 2:NXT, 3:통합 |

#### 요청 예시

```json
{
	"date" : "20240525",
	"amt_qty_tp" : "1",
	"mrkt_tp" : "0",
	"stex_tp" : "3"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| prm_trde_acc_trnsn | N | LIST | 프로그램매매누적추이 |
| - dt | N | String | 일자 |
| - kospi200 | N | String | KOSPI200 |
| - basis | N | String | BASIS |
| - dfrt_trde_tdy | N | String | 차익거래당일 |
| - dfrt_trde_acc | N | String | 차익거래누적 |
| - ndiffpro_trde_tdy | N | String | 비차익거래당일 |
| - ndiffpro_trde_acc | N | String | 비차익거래누적 |
| - all_tdy | N | String | 전체당일 |
| - all_acc | N | String | 전체누적 |

### ka90008 - 종목시간별프로그램매매추이요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| amt_qty_tp | Y | String | 금액수량구분 1:금액, 2:수량 |
| stk_cd | Y | String | 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |
| date | Y | String | 날짜 YYYYMMDD |

#### 요청 예시

```json
{
	"amt_qty_tp" : "1",
	"stk_cd" : "005930",
	"date" : "20241125"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_tm_prm_trde_trnsn | N | LIST | 종목시간별프로그램매매추이 |
| - tm | N | String | 시간 |
| - cur_prc | N | String | 현재가 |
| - pre_sig | N | String | 대비기호 |
| - pred_pre | N | String | 전일대비 |
| - flu_rt | N | String | 등락율 |
| - trde_qty | N | String | 거래량 |
| - prm_sell_amt | N | String | 프로그램매도금액 |
| - prm_buy_amt | N | String | 프로그램매수금액 |
| - prm_netprps_amt | N | String | 프로그램순매수금액 |
| - prm_netprps_amt_irds | N | String | 프로그램순매수금액증감 |
| - prm_sell_qty | N | String | 프로그램매도수량 |
| - prm_buy_qty | N | String | 프로그램매수수량 |
| - prm_netprps_qty | N | String | 프로그램순매수수량 |
| - prm_netprps_qty_irds | N | String | 프로그램순매수수량증감 |
| - base_pric_tm | N | String | 기준가시간 |
| - dbrt_trde_rpy_sum | N | String | 대차거래상환주수합 |
| - remn_rcvord_sum | N | String | 잔고수주합 |
| - stex_tp | N | String | 거래소구분 KRX , NXT , 통합 |

### ka90010 - 프로그램매매추이요청 일자별

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| date | Y | String | 날짜 YYYYMMDD |
| amt_qty_tp | Y | String | 금액수량구분 1:금액(백만원), 2:수량(천주) |
| mrkt_tp | Y | String | 시장구분 코스피- 거래소구분값 1일경우:P00101, 2일경우:P001_NX01, 3일경우:P001_AL01  코스닥- 거래소구분값 1일경우:P10102, 2일경우:P101_NX02, 3일경우:P001_AL02 |
| min_tic_tp | Y | String | 분틱구분 0:틱, 1:분 |
| stex_tp | Y | String | 거래소구분 1:KRX, 2:NXT 3.통합 |

#### 요청 예시

```json
{
	"date" : "20241125",
	"amt_qty_tp" : "1",
	"mrkt_tp" : "P00101",
	"min_tic_tp" : "0",
	"stex_tp" : "1"
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| prm_trde_trnsn | N | LIST | 프로그램매매추이 |
| - cntr_tm | N | String | 체결시간 |
| - dfrt_trde_sel | N | String | 차익거래매도 |
| - dfrt_trde_buy | N | String | 차익거래매수 |
| - dfrt_trde_netprps | N | String | 차익거래순매수 |
| - ndiffpro_trde_sel | N | String | 비차익거래매도 |
| - ndiffpro_trde_buy | N | String | 비차익거래매수 |
| - ndiffpro_trde_netprps | N | String | 비차익거래순매수 |
| - dfrt_trde_sell_qty | N | String | 차익거래매도수량 |
| - dfrt_trde_buy_qty | N | String | 차익거래매수수량 |
| - dfrt_trde_netprps_qty | N | String | 차익거래순매수수량 |
| - ndiffpro_trde_sell_qty | N | String | 비차익거래매도수량 |
| - ndiffpro_trde_buy_qty | N | String | 비차익거래매수수량 |
| - ndiffpro_trde_netprps_qty | N | String | 비차익거래순매수수량 |
| - all_sel | N | String | 전체매도 |
| - all_buy | N | String | 전체매수 |
| - all_netprps | N | String | 전체순매수 |
| - kospi200 | N | String | KOSPI200 |
| - basis | N | String | BASIS |

### ka90013 - 종목일별프로그램매매추이요청

- Endpoint: /api/dostk/mrkcond
- Protocol: REST

#### 요청 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| amt_qty_tp | N | String | 금액수량구분 1:금액, 2:수량 |
| stk_cd | Y | String | 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |
| date | N | String | 날짜 YYYYMMDD |

#### 요청 예시

```json
{
	"amt_qty_tp" : "",
	"stk_cd" : "005930",
	"date" : ""
}
```

#### 응답 필드

| 필드 | 필수 | 타입 | 설명 |
| --- | --- | --- | --- |
| stk_daly_prm_trde_trnsn | N | LIST | 종목일별프로그램매매추이 |
| - dt | N | String | 일자 |
| - cur_prc | N | String | 현재가 |
| - pre_sig | N | String | 대비기호 |
| - pred_pre | N | String | 전일대비 |
| - flu_rt | N | String | 등락율 |
| - trde_qty | N | String | 거래량 |
| - prm_sell_amt | N | String | 프로그램매도금액 |
| - prm_buy_amt | N | String | 프로그램매수금액 |
| - prm_netprps_amt | N | String | 프로그램순매수금액 |
| - prm_netprps_amt_irds | N | String | 프로그램순매수금액증감 |
| - prm_sell_qty | N | String | 프로그램매도수량 |
| - prm_buy_qty | N | String | 프로그램매수수량 |
| - prm_netprps_qty | N | String | 프로그램순매수수량 |
| - prm_netprps_qty_irds | N | String | 프로그램순매수수량증감 |
| - base_pric_tm | N | String | 기준가시간 |
| - dbrt_trde_rpy_sum | N | String | 대차거래상환주수합 |
| - remn_rcvord_sum | N | String | 잔고수주합 |
| - stex_tp | N | String | 거래소구분 KRX , NXT , 통합 |


