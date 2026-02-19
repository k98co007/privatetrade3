from __future__ import annotations

from datetime import date
from uuid import uuid4

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
          <th>9시3분 가격</th>
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
          <th>9시3분 가격</th>
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
          display(row.priceAt0903),
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

    @app.exception_handler(HTTPException)
    async def _handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = _request_id(request, None)
        code = "UAG_HTTP_ERROR"
        message = str(exc.detail) if exc.detail else "요청 처리 중 오류가 발생했습니다."
        payload = build_error_envelope(request_id=request_id, code=code, message=message)
        return JSONResponse(status_code=exc.status_code, content=payload)

    return app