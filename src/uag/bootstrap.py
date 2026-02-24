from __future__ import annotations

from datetime import date
from uuid import uuid4
import json

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from csm.errors import CsmValidationError

from .models import (
    ModeSwitchRequest,
    SettingsSaveRequest,
    TradingStartRequest,
    build_error_envelope,
    build_success_envelope,
)
from .service import UagService, map_csm_error
        


def _request_id(request: Request, header_value: str | None) -> str:
    if header_value:
        return header_value
    prior = getattr(request.state, "request_id", None)
    if prior:
        return prior
    request.state.request_id = f"req-{uuid4().hex[:12]}"
    return request.state.request_id


def create_app(
    *,
    settings_path: str = "runtime/config/settings.local.json",
    credentials_path: str = "runtime/config/credentials.local.json",
    prp_db_path: str = "runtime/state/prp.db",
) -> FastAPI:
    app = FastAPI(title="PrivateTrade UAG", version="0.1.0")
    service = UagService(settings_path=settings_path, credentials_path=credentials_path, prp_db_path=prp_db_path)

    @app.exception_handler(CsmValidationError)
    async def _handle_csm_validation(request: Request, exc: CsmValidationError) -> JSONResponse:
        request_id = _request_id(request, None)
        status_code, message = map_csm_error(exc)
        payload = build_error_envelope(
            request_id=request_id,
            code=exc.code,
            message=message,
            details=[{"field": exc.field, "reason": str(exc.value)}],
            retryable=False,
        )
        return JSONResponse(status_code=status_code, content=payload)

    @app.on_event("shutdown")
    async def _on_shutdown() -> None:
        service.shutdown()

    @app.get("/", response_class=HTMLResponse)
    async def ui_home() -> str:
        return """
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>PrivateTrade UAG</title>
</head>
<body style=\"font-family: sans-serif; max-width: 900px; margin: 24px auto; line-height: 1.4;\">
  <h1>PrivateTrade UAG</h1>

  <h2>Config Input</h2>
  <div>
    <label>Symbols (comma): <input id=\"symbols\" value=\"005930,000660\" /></label><br />
    <label>Mode:
      <select id=\"mode\">
        <option value=\"mock\">mock</option>
        <option value=\"live\">live</option>
      </select>
    </label>
    <label><input type=\"checkbox\" id=\"liveConfirm\" /> live confirmed</label><br />
    <label>buyBudget: <input id=\"buyBudget\" value=\"1000000\" /></label><br />
    <label>appKey: <input id=\"appKey\" value=\"demo\" /></label><br />
    <label>appSecret: <input id=\"appSecret\" value=\"demo\" /></label><br />
    <label>accountNo: <input id=\"accountNo\" value=\"12345678\" /></label><br />
    <label>userId: <input id=\"userId\" value=\"demo\" /></label><br />
    <button onclick=\"saveSettings()\">Save Settings</button>
  </div>

  <h2>Mock/Live Switch</h2>
  <div>
    <label>Target mode:
      <select id=\"targetMode\">
        <option value=\"mock\">mock</option>
        <option value=\"live\">live</option>
      </select>
    </label>
    <label><input type=\"checkbox\" id=\"switchConfirm\" /> live confirmed</label>
    <button onclick=\"switchMode()\">Switch</button>
  </div>

  <h2>Start Command</h2>
  <div>
    <label><input type=\"checkbox\" id=\"dryRun\" checked /> dry run</label>
    <button onclick=\"startTrading()\">Start</button>
  </div>

  <h2>Monitor Panel</h2>
  <div>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; width: 100%; font-size: 13px;">
      <thead>
        <tr>
          <th>종목명</th>
          <th>종목코드</th>
          <th>8시30분 가격</th>
          <th>현재 가격</th>
          <th>전저점 시간</th>
          <th>전저점 가격</th>
          <th>매수 시간</th>
          <th>매수 가격</th>
          <th>전고점 시간</th>
          <th>전고점 가격</th>
          <th>매도 시간</th>
          <th>매도 가격</th>
        </tr>
      </thead>
      <tbody id="monitorRows"></tbody>
    </table>
    <pre id="monitor"></pre>
  </div>

  <h2>Report Panel</h2>
  <div>
    <label>Date: <input id=\"reportDate\" placeholder=\"YYYY-MM-DD\" /></label>
    <button onclick=\"loadDaily()\">Daily Report</button>
    <button onclick=\"loadTrades()\">Trades Report</button>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; width: 100%; font-size: 13px; margin-top: 8px;">
      <thead>
        <tr>
          <th>종목명</th>
          <th>종목코드</th>
          <th>8시30분 가격</th>
          <th>현재 가격</th>
          <th>전저점 시간</th>
          <th>전저점 가격</th>
          <th>매수 시간</th>
          <th>매수 가격</th>
          <th>전고점 시간</th>
          <th>전고점 가격</th>
          <th>매도 시간</th>
          <th>매도 가격</th>
        </tr>
      </thead>
      <tbody id="reportRows"></tbody>
    </table>
    <pre id=\"reports\"></pre>
  </div>

  <script>
    async function postJson(url, body) {
      const response = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)
      });
      return response.json();
    }
    async function getJson(url) {
      const response = await fetch(url);
      return response.json();
    }
    function dateValue() {
      const raw = document.getElementById('reportDate').value.trim();
      return raw || new Date().toISOString().slice(0, 10);
    }
    const previousCurrentPriceByTbody = new Map();

    function normalizePriceValue(value) {
      if (value == null) {
        return null;
      }
      const text = String(value).trim();
      if (!text || text === '-') {
        return null;
      }
      const parsed = Number(text.replace(/,/g, ''));
      if (Number.isFinite(parsed)) {
        return parsed;
      }
      return text;
    }

    function comparePriceChange(previousValue, currentValue) {
      const prev = normalizePriceValue(previousValue);
      const curr = normalizePriceValue(currentValue);

      if (prev == null || curr == null) {
        return null;
      }
      if (typeof prev === 'number' && typeof curr === 'number') {
        if (curr > prev) {
          return 1;
        }
        if (curr < prev) {
          return -1;
        }
        return 0;
      }
      return String(prev) === String(curr) ? 0 : null;
    }

    function applyCurrentPriceHighlight(td, delta) {
      if (delta == null) {
        td.style.color = 'black';
        td.style.fontWeight = 'normal';
        return;
      }

      if (delta > 0) {
        td.style.color = 'red';
        td.style.fontWeight = 'normal';
      } else if (delta < 0) {
        td.style.color = 'blue';
        td.style.fontWeight = 'normal';
      } else {
        td.style.color = '#444444';
        td.style.fontWeight = 'normal';
      }
    }

    function display(value) {
      return value == null ? '-' : String(value);
    }
    function renderRows(tbodyId, rows) {
      const tbody = document.getElementById(tbodyId);
      tbody.innerHTML = '';
      if (!previousCurrentPriceByTbody.has(tbodyId)) {
        previousCurrentPriceByTbody.set(tbodyId, new Map());
      }
      const previousCurrentPriceBySymbol = previousCurrentPriceByTbody.get(tbodyId);
      for (const row of (rows || [])) {
        const tr = document.createElement('tr');
        const symbolKey = String(row.symbolCode || row.symbolName || '');
        const cells = [
          display(row.symbolName),
          display(row.symbolCode),
          display(row.priceAt0830),
          display(row.currentPrice),
          display(row.previousLowTime),
          display(row.previousLowPrice),
          display(row.buyTime),
          display(row.buyPrice),
          display(row.previousHighTime),
          display(row.previousHighPrice),
          display(row.sellTime),
          display(row.sellPrice),
        ];
        for (const [index, text] of cells.entries()) {
          const td = document.createElement('td');
          td.textContent = text;
          if (index === 3) {
            const previousValue = previousCurrentPriceBySymbol.get(symbolKey);
            const delta = comparePriceChange(previousValue, row.currentPrice);
            applyCurrentPriceHighlight(td, delta);
          }
          tr.appendChild(td);
        }
        previousCurrentPriceBySymbol.set(symbolKey, row.currentPrice);
        tbody.appendChild(tr);
      }
    }
    async function saveSettings() {
      const symbols = document.getElementById('symbols').value.split(',').map(s => s.trim()).filter(Boolean);
      const payload = {
        watchSymbols: symbols,
        mode: document.getElementById('mode').value,
        liveModeConfirmed: document.getElementById('liveConfirm').checked,
        buyBudget: document.getElementById('buyBudget').value,
        credential: {
          appKey: document.getElementById('appKey').value,
          appSecret: document.getElementById('appSecret').value,
          accountNo: document.getElementById('accountNo').value,
          userId: document.getElementById('userId').value,
        }
      };
      const response = await postJson('/api/settings', payload);
      document.getElementById('monitor').textContent = JSON.stringify(response, null, 2);
      await loadStatus();
    }
    async function switchMode() {
      const payload = {
        targetMode: document.getElementById('targetMode').value,
        liveModeConfirmed: document.getElementById('switchConfirm').checked,
      };
      const response = await postJson('/api/mode/switch', payload);
      document.getElementById('monitor').textContent = JSON.stringify(response, null, 2);
      await loadStatus();
    }
    async function startTrading() {
      const payload = { dryRun: document.getElementById('dryRun').checked };
      const response = await postJson('/api/trading/start', payload);
      document.getElementById('monitor').textContent = JSON.stringify(response, null, 2);
      await loadStatus();
    }
    async function loadStatus() {
      const response = await getJson('/api/monitor/status');
      document.getElementById('monitor').textContent = JSON.stringify(response, null, 2);
      const rows = response && response.data ? response.data.monitoringRows : [];
      renderRows('monitorRows', rows);
    }
    async function loadDaily() {
      const dt = dateValue();
      const response = await getJson('/api/reports/daily?date=' + encodeURIComponent(dt));
      document.getElementById('reports').textContent = JSON.stringify(response, null, 2);
      const rows = response && response.data ? response.data.monitoringRows : [];
      renderRows('reportRows', rows);
    }
    async function loadTrades() {
      const dt = dateValue();
      const response = await getJson('/api/reports/trades?date=' + encodeURIComponent(dt));
      document.getElementById('reports').textContent = JSON.stringify(response, null, 2);
      const rows = response && response.data ? response.data.monitoringRows : [];
      renderRows('reportRows', rows);
    }
    loadStatus();
    setInterval(loadStatus, 3000);
  </script>
</body>
</html>
        """

    @app.post("/api/settings")
    async def save_settings(
        body: SettingsSaveRequest,
        request: Request,
        x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    ) -> dict:
        request_id = _request_id(request, x_request_id)
        data = service.save_settings(body.model_dump())
        return build_success_envelope(request_id=request_id, data=data)

    @app.post("/api/mode/switch")
    async def switch_mode(
        body: ModeSwitchRequest,
        request: Request,
        x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    ) -> dict:
        request_id = _request_id(request, x_request_id)
        data = service.switch_mode(target_mode=body.targetMode, live_mode_confirmed=body.liveModeConfirmed)
        return build_success_envelope(request_id=request_id, data=data)

    @app.post("/api/trading/start", status_code=202)
    async def start_trading(
        body: TradingStartRequest,
        request: Request,
        x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    ) -> dict:
        request_id = _request_id(request, x_request_id)
        try:
            data = service.start_trading(trading_date=body.tradingDate, dry_run=body.dryRun)
        except RuntimeError as exc:
            if str(exc) == "UAG_ENGINE_ALREADY_RUNNING":
                payload = build_error_envelope(
                    request_id=request_id,
                    code="UAG_ENGINE_ALREADY_RUNNING",
                    message="이미 엔진이 실행 중입니다.",
                    retryable=False,
                )
                return JSONResponse(status_code=409, content=payload)
            raise
        return build_success_envelope(request_id=request_id, data=data)

    @app.get("/api/monitor/status")
    async def monitor_status(
        request: Request,
        x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    ) -> dict:
        request_id = _request_id(request, x_request_id)
        data = service.monitor_status()
        return build_success_envelope(request_id=request_id, data=data)

    @app.get("/api/reports/daily")
    async def reports_daily(
        request: Request,
        date_value: date = Query(alias="date"),
        x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    ) -> dict:
        request_id = _request_id(request, x_request_id)
        data = service.get_daily_report(trading_date=date_value)
        return build_success_envelope(request_id=request_id, data=data)

    @app.get("/api/reports/trades")
    async def reports_trades(
        request: Request,
        date_value: date = Query(alias="date"),
        x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    ) -> dict:
        request_id = _request_id(request, x_request_id)
        data = service.get_trades_report(trading_date=date_value)
        return build_success_envelope(request_id=request_id, data=data)

    @app.get("/backtest", response_class=HTMLResponse)
    async def backtest_ui() -> str:
        creds = service.get_masked_credentials()
        date_text = date.today().isoformat()
        appkey = creds.get('appKey') or ''
        account_no = creds.get('accountNo') or ''
        html = """
<!doctype html>
<html lang="ko"> 
<head>
  <meta charset="utf-8"> 
  <meta name="viewport" content="width=device-width, initial-scale=1"> 
  <title>Backtest Viewer</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    .chart-wrap { overflow-x: auto; padding-bottom: 12px; }
    .chart-canvas { height: 360px; }
    .controls { max-width: 900px; margin: 12px 0; }
  </style>
</head>
<body style="font-family: sans-serif; max-width: 960px; margin: 18px auto;">
  <h1>백테스팅 차트</h1>
  <div class="controls">
    <label>종목코드: <input id="symbol" value="005930" /></label>
    <label>날짜: <input id="date" type="date" value="{DATE}" /></label>
    <label>분봉: 
      <select id="tf">
        <option value="1">1분</option>
        <option value="3">3분</option>
        <option value="5">5분</option>
        <option value="10">10분</option>
      </select>
    </label>
    <button id="btn">조회</button>
    <div>저장된 사용자 정보: appKey={APPKEY}, accountNo={ACCT}</div>
  </div>

  <div class="chart-wrap" id="wrap"> 
    <canvas id="chart" class="chart-canvas"></canvas>
  </div>

  <script>
    async function getJson(url) { const r = await fetch(url); return r.json(); }
    function makeCanvasWidth(points) { return Math.max(900, points * 6); }

    // Manual canvas-based candlestick renderer with tooltip, axes, zoom and pan
    function priceToY(price, minP, maxP, height, pad) {
      const r = (price - minP) / (maxP - minP || 1);
      return height - pad - r * (height - pad * 2);
    }

    // Chart state for pan/zoom
    window._btState = { offset: 0, step: 8 };

    function drawAxes(ctx, width, height, pad, minP, maxP, labels, state) {
      // Y axis labels
      ctx.fillStyle = '#000';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      for (let i = 0; i <= 4; i++) {
        const y = pad + (i / 4) * (height - pad * 2);
        const price = (maxP - (i / 4) * (maxP - minP)).toFixed(2);
        ctx.fillText(price, Math.max(40, 60) - 6, y);
      }

      // X axis labels (sparse)
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const visibleCount = Math.floor(width / state.step);
      const startIdx = Math.max(0, Math.floor(state.offset));
      const stepLabel = Math.max(1, Math.floor(visibleCount / 8));
      for (let i = 0; i < visibleCount; i += stepLabel) {
        const idx = startIdx + i;
        if (idx >= labels.length) break;
        const x = i * state.step + state.step * 0.5 + 60;
        ctx.fillText(labels[idx], x, height - pad + 4);
      }
    }

    function render(data, tf) {
      const canvas = document.getElementById('chart');
      const ctx = canvas.getContext('2d');
      const n = data.length;
      const state = window._btState;
      const step = state.step;
      const visibleWidth = Math.max(900, Math.floor(n * step));
      const height = 360;
      const pad = 30;
      const yAxisWidth = 60;

      canvas.width = visibleWidth + yAxisWidth;
      canvas.height = height;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      if (!n) return;

      const highs = data.map(d => d.high);
      const lows = data.map(d => d.low);
      const minP = Math.min(...lows);
      const maxP = Math.max(...highs);

      // background
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // grid lines
      ctx.strokeStyle = '#eee'; ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i++) {
        const y = pad + (i / 4) * (height - pad * 2);
        ctx.beginPath(); ctx.moveTo(yAxisWidth, y); ctx.lineTo(canvas.width, y); ctx.stroke();
      }

      // draw candles (consider offset)
      const offset = Math.max(0, Math.min(n - 1, Math.floor(state.offset)));
      const visibleCount = Math.min(n - offset, Math.floor((canvas.width - yAxisWidth) / step));
      for (let i = 0; i < visibleCount; i++) {
        const idx = offset + i;
        const d = data[idx];
        const x = yAxisWidth + i * step + step * 0.5;
        const yHigh = priceToY(d.high, minP, maxP, height, pad);
        const yLow = priceToY(d.low, minP, maxP, height, pad);
        const yOpen = priceToY(d.open, minP, maxP, height, pad);
        const yClose = priceToY(d.close, minP, maxP, height, pad);

        // wick
        ctx.beginPath(); ctx.strokeStyle = '#222'; ctx.lineWidth = 1; ctx.moveTo(x, yHigh); ctx.lineTo(x, yLow); ctx.stroke();

        // body
        const bodyWidth = Math.max(1, step * 0.6);
        const top = Math.min(yOpen, yClose);
        const bodyHeight = Math.max(1, Math.abs(yClose - yOpen));
        ctx.fillStyle = d.close >= d.open ? '#d32f2f' : '#1565c0';
        ctx.fillRect(x - bodyWidth / 2, top, bodyWidth, bodyHeight);
      }

      // axes labels and ticks
      drawAxes(ctx, canvas.width - yAxisWidth, height, pad, minP, maxP, data.map(d => d.time), state);

      // tooltip element
      let tip = document.getElementById('bt-tooltip');
      if (!tip) {
        tip = document.createElement('div');
        tip.id = 'bt-tooltip';
        tip.style.position = 'absolute';
        tip.style.pointerEvents = 'none';
        tip.style.background = 'rgba(0,0,0,0.7)';
        tip.style.color = '#fff';
        tip.style.padding = '6px 8px';
        tip.style.borderRadius = '4px';
        tip.style.fontSize = '12px';
        tip.style.display = 'none';
        document.body.appendChild(tip);
      }

      // attach interactions
      let isPanning = false;
      let lastX = 0;
      canvas.onwheel = function (e) {
        e.preventDefault();
        const delta = Math.sign(e.deltaY);
        // zoom: change step
        state.step = Math.max(4, Math.min(40, state.step - delta));
        render(data, tf);
      };
      canvas.onmousedown = function (e) {
        isPanning = true; lastX = e.clientX;
      };
      window.onmouseup = function () { isPanning = false; };
      window.onmousemove = function (e) {
        if (isPanning) {
          const dx = e.clientX - lastX; lastX = e.clientX;
          state.offset = Math.max(0, Math.min(n - 1, state.offset - dx / state.step));
          render(data, tf);
          return;
        }
      };

      canvas.onmousemove = function (e) {
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left - yAxisWidth;
        const idx = offset + Math.floor(x / state.step);
        const tip = document.getElementById('bt-tooltip');
        if (idx >= 0 && idx < n) {
          const d = data[idx];
          tip.style.display = 'block';
          tip.style.left = (e.clientX + 12) + 'px';
          tip.style.top = (e.clientY + 12) + 'px';
          tip.innerHTML = `<b>${d.time}</b><br/>O:${d.open} H:${d.high} L:${d.low} C:${d.close}`;
        } else {
          tip.style.display = 'none';
        }
      };

      canvas.onmouseleave = function () { const t = document.getElementById('bt-tooltip'); if (t) t.style.display = 'none'; };

    }

    document.getElementById('btn').addEventListener('click', async () => {
      const symbol = document.getElementById('symbol').value.trim();
      const date = document.getElementById('date').value;
      const tf = Number(document.getElementById('tf').value || 1);
      if (!symbol || !date) return alert('종목코드와 날짜를 입력하세요');
      const url = `/api/backtest/minutes?symbol=${encodeURIComponent(symbol)}&date=${encodeURIComponent(date)}&timeframe=${encodeURIComponent(tf)}`;
      const resp = await getJson(url);
      if (!resp || !resp.data) return alert('데이터를 불러오지 못했습니다');
      render(resp.data.minutes, tf);
    });
  </script>
</body>
</html>
"""
        html = html.replace("{DATE}", date_text).replace("{APPKEY}", str(appkey)).replace("{ACCT}", str(account_no))
        return html

    @app.get("/api/backtest/minutes")
    async def backtest_minutes(
        request: Request,
        symbol: str = Query(...),
        date_value: date = Query(alias="date"),
        timeframe: int = Query(default=1, alias="timeframe"),
        x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    ) -> dict:
        request_id = _request_id(request, x_request_id)

        # Try to fetch minute chart from Kiwoom chart API (ka10080). Fall back to synthetic data.
        try:
            from kia.api_client import RoutingKiaApiClient

            settings = service.repository.read_settings()
            mode = settings.get("mode", "mock")
            client = RoutingKiaApiClient(csm_repository=service.repository)
            base_dt = date_value.strftime("%Y%m%d")
            # Request the API for the desired timeframe (tic_scope). Do not force 1-minute and re-aggregate locally.
            tic_scope = str(timeframe) if timeframe and timeframe > 1 else "1"
            payload = {"stk_cd": symbol, "tic_scope": tic_scope, "upd_stkpc_tp": "1", "base_dt": base_dt}
            raw = client.call(service_type="chart", mode=mode, payload=payload, api_id="ka10080")
            try:
              raw_text = json.dumps(raw, ensure_ascii=False, default=str)
            except Exception:
              raw_text = str(raw)
            rows = raw.get("stk_min_pole_chart_qry") or raw.get("min_chart") or []
            bars: list[dict] = []
            for row in rows:
              if not isinstance(row, dict):
                continue
              tm = str(row.get("cntr_tm") or row.get("time") or "").strip()
              digits = "".join(ch for ch in tm if ch.isdigit())
              if len(digits) < 6:
                continue
              # Ensure the row belongs to the requested trading date by looking
              # for YYYYMMDD anywhere in the digit string. If not present,
              # skip the row (avoids mixing bars from other dates).
              target_ymd = date_value.strftime("%Y%m%d")
              if target_ymd not in digits:
                continue
              hh = digits[-6:-4]
              mm = digits[-4:-2]
              time_label = f"{int(hh):02d}:{int(mm):02d}"

              def _to_float(val):
                try:
                  return abs(float(str(val).replace(",", "")))
                except Exception:
                  return None

              open_p = _to_float(row.get("open_pric") or row.get("open") or row.get("open_price"))
              high_p = _to_float(row.get("high_pric") or row.get("high") or row.get("high_price"))
              low_p = _to_float(row.get("low_pric") or row.get("low") or row.get("low_price"))
              close_p = _to_float(row.get("cur_prc") or row.get("price") or row.get("prc") or row.get("close"))

              # If close is missing/unparseable, skip the row (cannot chart without close)
              if close_p is None:
                continue

              # Use sensible fallbacks for open/high/low if the API omitted them
              if open_p is None:
                open_p = close_p
              if high_p is None:
                high_p = max(open_p, close_p)
              if low_p is None:
                low_p = min(open_p, close_p)

              # normalize volume (Kiwoom field is `trde_qty` per docs)
              vol_raw = row.get("trde_qty") or row.get("trd_qty") or row.get("vol") or row.get("volume") or 0
              try:
                volume = abs(int(vol_raw))
              except Exception:
                try:
                  volume = abs(int(float(vol_raw)))
                except Exception:
                  volume = 0

              bars.append({"time": time_label, "open": open_p, "high": high_p, "low": low_p, "close": close_p, "volume": volume})

            if not bars:
                raise RuntimeError("no_chart_rows")

            # ensure chronological order (API may return newest-first)
            def _time_key(item: dict) -> int:
              hh, mm = item["time"].split(":")
              return int(hh) * 60 + int(mm)

            bars.sort(key=_time_key)

            # Assume the API returned bars at the requested `tic_scope` (timeframe).
            minutes = bars

            return build_success_envelope(request_id=request_id, data={"minutes": minutes, "symbol": symbol, "date": date_value.isoformat(), "timeframe": timeframe, "raw": raw_text})
        except Exception:
            # fallback to deterministic synthetic data
            from random import Random

            seed = f"{symbol}-{date_value.isoformat()}-{timeframe}"
            rng = Random(seed)
            total_minutes = 390
            base_price = 10000 + (abs(hash(symbol)) % 5000)
            bars = []
            price = float(base_price)
            for i in range(total_minutes):
                change = (rng.random() - 0.48) * (rng.random() * 4)
                # compute raw values then convert to absolute (ignore any leading minus signs)
                raw_open = price
                raw_close = max(1.0, price + change)
                raw_high = max(raw_open, raw_close) + rng.random() * 2
                raw_low = min(raw_open, raw_close) - rng.random() * 2
                open_p = abs(raw_open)
                close_p = abs(raw_close)
                # ensure high/low honor absolute semantics
                high_p = max(open_p, close_p, abs(raw_high))
                low_p = min(open_p, close_p, abs(raw_low))
                volume = abs(rng.randint(100, 1000))
                hh = 9 + (i // 60)
                mm = i % 60
                time_label = f"{hh:02d}:{mm:02d}"
                bars.append({"time": time_label, "open": round(open_p, 2), "high": round(high_p, 2), "low": round(low_p, 2), "close": round(close_p, 2), "volume": volume})
                price = close_p

            # ensure chronological order for synthetic data as well
            def _time_key_synth(item: dict) -> int:
              hh, mm = item["time"].split(":")
              return int(hh) * 60 + int(mm)

            bars.sort(key=_time_key_synth)

            # Aggregate synthetic minute bars to requested timeframe when needed
            if timeframe is None or timeframe <= 1:
              minutes = bars
            else:
              minutes = []
              for i in range(0, len(bars), timeframe):
                chunk = bars[i : i + timeframe]
                if not chunk:
                  continue
                minutes.append(
                  {
                    "time": chunk[0]["time"],
                    "open": chunk[0]["open"],
                    "high": max(c["high"] for c in chunk),
                    "low": min(c["low"] for c in chunk),
                    "close": chunk[-1]["close"],
                    "volume": sum(c["volume"] for c in chunk),
                  }
                )

            return build_success_envelope(request_id=request_id, data={"minutes": minutes, "symbol": symbol, "date": date_value.isoformat(), "timeframe": timeframe, "raw": None})

    @app.exception_handler(HTTPException)
    async def _handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = _request_id(request, None)
        code = "UAG_HTTP_ERROR"
        message = str(exc.detail) if exc.detail else "요청 처리 중 오류가 발생했습니다."
        payload = build_error_envelope(request_id=request_id, code=code, message=message)
        return JSONResponse(status_code=exc.status_code, content=payload)

    return app