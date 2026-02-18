from __future__ import annotations

import os
import threading
import time
from datetime import date, datetime, time as dt_time
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any

from csm.errors import CsmValidationError
from csm.masking import to_masked_credential
from csm.repository import CsmRuntimeRepository
from csm.service import CsmService
from kia.contracts import Mode, SubmitOrderRequest
from kia.gateway import DefaultKiaGateway
from opm.service import OpmService
from prp.repository import PrpRepository
from tse.models import PlaceBuyOrderCommand, PlaceSellOrderCommand
from tse.quote_monitoring import QuoteMonitoringConfig, QuoteMonitoringLoop
from tse.service import TseService

from .models import MonitoringSnapshot, RuntimeState


REFERENCE_CAPTURE_TIME = dt_time(hour=9, minute=3, second=0)
MARKET_CLOSE_TIME = dt_time(hour=15, minute=30, second=0)


class UagService:
    def __init__(
        self,
        *,
        settings_path: str = "runtime/config/settings.local.json",
        credentials_path: str = "runtime/config/credentials.local.json",
        prp_db_path: str = "runtime/state/prp.db",
    ) -> None:
        self.repository = CsmRuntimeRepository(settings_path=settings_path, credentials_path=credentials_path)
        self.csm_service = CsmService(repository=self.repository)
        self.prp_db_path = prp_db_path
        self.state = RuntimeState()
        self._quote_loop: QuoteMonitoringLoop | None = None
        self._quote_loop_thread: threading.Thread | None = None
        self._quote_loop_stop = threading.Event()
        self._quote_loop_lock = threading.Lock()
        self._order_gateway: DefaultKiaGateway | None = None
        self._ensure_runtime_files()

    def _ensure_runtime_files(self) -> None:
        os.makedirs(os.path.dirname(self.repository.settings_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.repository.credentials_path), exist_ok=True)

        if not os.path.exists(self.repository.settings_path):
            self.repository.write_settings(
                {
                    "version": "v0.1.0",
                    "updatedAt": datetime.now().astimezone().isoformat(),
                    "watchSymbols": ["005930"],
                    "mode": "mock",
                    "liveModeConfirmed": False,
                    "credentialsRef": "cred-default",
                }
            )

        if not os.path.exists(self.repository.credentials_path):
            self.repository.write_credentials(
                {
                    "credentialsId": "cred-default",
                    "updatedAt": datetime.now().astimezone().isoformat(),
                    "provider": "kiwoom-rest",
                    "credential": {
                        "appKey": "",
                        "appSecret": "",
                        "accountNo": "",
                        "userId": "",
                    },
                }
            )

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.csm_service.save_settings(payload)

    def switch_mode(self, *, target_mode: str, live_mode_confirmed: bool) -> dict[str, Any]:
        guard = {
            "openOrders": 0,
            "openPositions": 0,
            "engineState": "IDLE" if self.state.engine_state == "IDLE" else "RUNNING",
        }
        return self.csm_service.switch_mode(target_mode, live_mode_confirmed, guard)

    def start_trading(self, *, trading_date: date | None, dry_run: bool) -> dict[str, Any]:
        if self.state.engine_state == "RUNNING":
            raise RuntimeError("UAG_ENGINE_ALREADY_RUNNING")

        self.state.engine_state = "RUNNING"
        self.state.trading_started_at = datetime.now().astimezone()
        self.state.trading_date = trading_date or date.today()
        self.state.dry_run = dry_run
        self._start_quote_monitoring_loop()

        return {
            "engineState": self.state.engine_state,
            "acceptedAt": self.state.trading_started_at.isoformat(),
            "tradingDate": self.state.trading_date.isoformat(),
            "dryRun": self.state.dry_run,
            "safeMode": True,
        }

    def monitor_status(self) -> dict[str, Any]:
        settings = self.repository.read_settings()
        watch_symbols = settings.get("watchSymbols", [])

        return {
            "engineState": self.state.engine_state,
            "mode": settings.get("mode", "mock"),
            "watchSymbols": watch_symbols,
            "startedAt": self.state.trading_started_at.isoformat() if self.state.trading_started_at else None,
            "tradingDate": self.state.trading_date.isoformat() if self.state.trading_date else None,
            "dryRun": self.state.dry_run,
            "safeMode": True,
            "openOrders": 0,
            "openPositions": 0,
            "monitoringRows": self._build_monitoring_rows(watch_symbols=watch_symbols, use_close_price_current=False),
            "quoteMonitoring": {
                "loopState": self.state.quote_loop_state,
                "cyclesTotal": self.state.quote_cycles_total,
                "lastPollCycleId": self.state.quote_last_poll_cycle_id,
                "lastCycleAt": self.state.quote_last_cycle_at.isoformat() if self.state.quote_last_cycle_at else None,
                "lastCyclePartial": self.state.quote_last_cycle_partial,
                "lastQuoteCount": self.state.quote_last_quote_count,
                "lastErrorCount": self.state.quote_last_error_count,
                "lastCommandCount": self.state.quote_last_command_count,
                "lastStrategyEventCount": self.state.quote_last_strategy_event_count,
                "lastCycleError": self.state.quote_last_cycle_error,
            },
        }

    def shutdown(self) -> None:
        self.state.engine_state = "IDLE"
        self._stop_quote_monitoring_loop()

    def get_daily_report(self, trading_date: date) -> dict[str, Any]:
        with PrpRepository(db_path=self.prp_db_path) as repo:
            report = repo.generate_daily_report(trading_date)

        settings = self.repository.read_settings()
        watch_symbols = settings.get("watchSymbols", [])

        return {
            "tradingDate": report.trading_date.isoformat(),
            "totalBuyAmount": str(report.total_buy_amount),
            "totalSellAmount": str(report.total_sell_amount),
            "totalSellTax": str(report.total_sell_tax),
            "totalSellFee": str(report.total_sell_fee),
            "totalNetPnl": str(report.total_net_pnl),
            "totalReturnRate": str(report.total_return_rate),
            "generatedAt": report.generated_at.isoformat(),
            "monitoringRows": self._build_monitoring_rows(
                watch_symbols=watch_symbols,
                use_close_price_current=True,
                trading_date=trading_date,
            ),
        }

    def get_trades_report(self, trading_date: date) -> dict[str, Any]:
        with PrpRepository(db_path=self.prp_db_path) as repo:
            details = repo.list_trade_details(trading_date)
            if not details:
                repo.generate_daily_report(trading_date)
                details = repo.list_trade_details(trading_date)

        settings = self.repository.read_settings()
        watch_symbols = settings.get("watchSymbols", [])

        return {
            "tradingDate": trading_date.isoformat(),
            "count": len(details),
            "items": [
                {
                    "id": detail.id,
                    "symbol": detail.symbol,
                    "buyExecutedAt": detail.buy_executed_at.isoformat(),
                    "sellExecutedAt": detail.sell_executed_at.isoformat(),
                    "quantity": detail.quantity,
                    "buyPrice": str(detail.buy_price),
                    "sellPrice": str(detail.sell_price),
                    "buyAmount": str(detail.buy_amount),
                    "sellAmount": str(detail.sell_amount),
                    "sellTax": str(detail.sell_tax),
                    "sellFee": str(detail.sell_fee),
                    "netPnl": str(detail.net_pnl),
                    "returnRate": str(detail.return_rate),
                }
                for detail in details
            ],
            "monitoringRows": self._build_monitoring_rows(
                watch_symbols=watch_symbols,
                use_close_price_current=True,
                trading_date=trading_date,
            ),
        }

    def get_masked_credentials(self) -> dict[str, str]:
        credential_payload = self.repository.read_credentials()
        credential = credential_payload.get("credential", {})
        normalized = {
            "appKey": str(credential.get("appKey", "")),
            "appSecret": str(credential.get("appSecret", "")),
            "accountNo": str(credential.get("accountNo", "")),
            "userId": str(credential.get("userId", "")),
        }
        return to_masked_credential(normalized)

    def _start_quote_monitoring_loop(self) -> None:
        with self._quote_loop_lock:
            self._stop_quote_monitoring_loop()

            settings = self.repository.read_settings()
            watch_symbols = [str(symbol) for symbol in settings.get("watchSymbols", ["005930"]) if str(symbol).strip()]
            mode_raw = str(settings.get("mode", "mock"))
            mode = mode_raw if mode_raw in {"mock", "live"} else "mock"

            self._quote_loop_stop.clear()
            tse_service = TseService(trading_date=self.state.trading_date or date.today(), watch_symbols=watch_symbols)
            self._order_gateway = DefaultKiaGateway(csm_repository=self.repository)
            self._quote_loop = QuoteMonitoringLoop(
                tse_service=tse_service,
                kia_gateway=self._order_gateway,
                config=QuoteMonitoringConfig(mode=mode),
            )

            self.state.quote_loop_state = "RUNNING"
            self.state.quote_last_cycle_error = None

            self._quote_loop_thread = threading.Thread(
                target=self._quote_monitor_worker,
                name="uag-quote-monitor",
                daemon=True,
            )
            self._quote_loop_thread.start()

    def _stop_quote_monitoring_loop(self) -> None:
        self._quote_loop_stop.set()
        thread = self._quote_loop_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

        if self._quote_loop is not None:
            self._quote_loop.stop()

        self._quote_loop_thread = None
        self._quote_loop = None
        self._order_gateway = None
        self.state.quote_loop_state = "STOPPED"

    def _quote_monitor_worker(self) -> None:
        if self._quote_loop is None:
            return

        self._quote_loop.start()
        interval_seconds = self._quote_loop.poll_interval_seconds

        while not self._quote_loop_stop.is_set() and self.state.engine_state == "RUNNING":
            cycle = self._quote_loop.run_cycle()
            self._update_monitoring_snapshots(cycle)
            self.state.quote_loop_state = cycle.state
            self.state.quote_cycles_total += 1
            self.state.quote_last_poll_cycle_id = cycle.poll_cycle_id
            self.state.quote_last_cycle_at = datetime.now().astimezone()
            self.state.quote_last_cycle_partial = cycle.partial
            self.state.quote_last_quote_count = cycle.quote_count
            self.state.quote_last_error_count = cycle.error_count
            self.state.quote_last_cycle_error = cycle.fetch_error
            self.state.quote_last_command_count = sum(len(output.commands) for output in cycle.outputs)
            self.state.quote_last_strategy_event_count = sum(len(output.strategy_events) for output in cycle.outputs)

            if not self.state.dry_run:
                self._execute_cycle_commands(cycle.outputs)

            if self._quote_loop_stop.is_set() or self.state.engine_state != "RUNNING":
                break
            time.sleep(interval_seconds)

    def _execute_cycle_commands(self, outputs: list) -> None:
        for output in outputs:
            for command in output.commands:
                self._execute_tse_command(command)

    def _execute_tse_command(self, command: PlaceBuyOrderCommand | PlaceSellOrderCommand) -> None:
        if self._order_gateway is None:
            return

        mode, account_no = self._read_order_execution_context()
        side = "BUY" if isinstance(command, PlaceBuyOrderCommand) else "SELL"
        quantity = self._resolve_order_quantity(side=side, order_price=command.order_price)
        if quantity <= 0:
            return
        now = datetime.now().astimezone()

        with PrpRepository(db_path=self.prp_db_path) as repo:
            opm_service = OpmService(prp_repository=repo, kia_gateway=self._order_gateway)
            order = opm_service.create_order(
                trading_date=command.trading_date,
                symbol=command.symbol,
                side=side,
                requested_price=command.order_price,
                requested_qty=quantity,
                now=now,
                client_order_id=command.command_id,
            )
            order = opm_service.move_order_status(order=order, next_status="SUBMITTED", now=datetime.now().astimezone())

            try:
                result = self._order_gateway.submit_order(
                    SubmitOrderRequest(
                        mode=mode,
                        account_no=account_no,
                        symbol=command.symbol,
                        side=side,
                        order_type="LIMIT",
                        price=command.order_price,
                        quantity=quantity,
                        client_order_id=order.client_order_id,
                    )
                )
            except Exception:
                opm_service.move_order_status(
                    order=order,
                    next_status="REJECTED",
                    now=datetime.now().astimezone(),
                    last_error_code="OPM_KIA_SUBMIT_FAILED",
                )
                return

            final_status = "ACCEPTED" if result.status == "ACCEPTED" else "REJECTED"
            opm_service.move_order_status(
                order=order,
                next_status=final_status,
                now=datetime.now().astimezone(),
                broker_order_id=result.broker_order_id or None,
                last_error_code=None if final_status == "ACCEPTED" else "OPM_KIA_ORDER_REJECTED",
            )

    def _read_order_execution_context(self) -> tuple[Mode | None, str]:
        settings = self.repository.read_settings()
        mode_value = str(settings.get("mode", "mock"))
        mode: Mode | None = mode_value if mode_value in {"mock", "live"} else None

        credential_payload = self.repository.read_credentials()
        credential = credential_payload.get("credential", {})
        account_no = str(credential.get("accountNo", "")).strip() or "00000000"
        return mode, account_no

    def _resolve_order_quantity(self, *, side: str, order_price: Decimal) -> int:
        if side != "BUY":
            return 1
        if order_price <= 0:
            return 0

        settings = self.repository.read_settings()
        raw_budget = settings.get("buyBudget")
        if raw_budget is None:
            return 1

        budget_text = str(raw_budget).strip().replace(",", "")
        if not budget_text:
            return 1

        try:
            budget = Decimal(budget_text)
        except (InvalidOperation, ValueError):
            return 1

        if budget <= 0:
            return 0

        return int((budget / order_price).to_integral_value(rounding=ROUND_DOWN))

    def _snapshot_for_symbol(self, symbol: str) -> MonitoringSnapshot:
        snapshot = self.state.monitoring_snapshots.get(symbol)
        if snapshot is None:
            snapshot = MonitoringSnapshot(symbol_code=symbol, symbol_name=symbol)
            self.state.monitoring_snapshots[symbol] = snapshot
        return snapshot

    def _update_monitoring_snapshots(self, cycle: Any) -> None:
        for quote in cycle.quotes:
            snapshot = self._snapshot_for_symbol(quote.symbol)
            quote_time = quote.as_of
            quote_price = quote.price

            if snapshot.price_at_0903 is None and quote_time.time() >= REFERENCE_CAPTURE_TIME:
                snapshot.price_at_0903 = quote_price

            snapshot.current_price = quote_price

            if snapshot.previous_low_price is None or quote_price <= snapshot.previous_low_price:
                snapshot.previous_low_price = quote_price
                snapshot.previous_low_time = quote_time

            if snapshot.previous_high_price is None or quote_price >= snapshot.previous_high_price:
                snapshot.previous_high_price = quote_price
                snapshot.previous_high_time = quote_time

            if snapshot.current_price_at_close is None and quote_time.time() >= MARKET_CLOSE_TIME:
                snapshot.current_price_at_close = quote_price

        for output in cycle.outputs:
            buy_signal_times: dict[str, datetime] = {}
            sell_signal_times: dict[str, datetime] = {}
            for event in output.strategy_events:
                if event.event_type == "BUY_SIGNAL":
                    buy_signal_times[event.symbol] = event.occurred_at
                if event.event_type == "SELL_SIGNAL":
                    sell_signal_times[event.symbol] = event.occurred_at

            for command in output.commands:
                snapshot = self._snapshot_for_symbol(command.symbol)
                if isinstance(command, PlaceBuyOrderCommand):
                    snapshot.buy_time = buy_signal_times.get(command.symbol, datetime.now().astimezone())
                    snapshot.buy_price = command.order_price
                elif isinstance(command, PlaceSellOrderCommand):
                    snapshot.sell_time = sell_signal_times.get(command.symbol, datetime.now().astimezone())
                    snapshot.sell_price = command.order_price

    def _build_monitoring_rows(
        self,
        *,
        watch_symbols: list[str],
        use_close_price_current: bool,
        trading_date: date | None = None,
    ) -> list[dict[str, Any]]:
        if trading_date is not None and self.state.trading_date != trading_date:
            return []

        ordered_symbols = [str(symbol) for symbol in watch_symbols if str(symbol).strip()]
        rows: list[dict[str, Any]] = []
        for symbol in ordered_symbols:
            snapshot = self.state.monitoring_snapshots.get(symbol)
            if snapshot is None:
                snapshot = MonitoringSnapshot(symbol_code=symbol, symbol_name=symbol)

            current_price = snapshot.current_price_at_close if use_close_price_current else snapshot.current_price
            if current_price is None:
                current_price = snapshot.current_price

            rows.append(
                {
                    "symbolName": snapshot.symbol_name,
                    "symbolCode": snapshot.symbol_code,
                    "priceAt0903": to_decimal_string(snapshot.price_at_0903) if snapshot.price_at_0903 is not None else None,
                    "currentPrice": to_decimal_string(current_price) if current_price is not None else None,
                    "previousLowTime": self._format_hms(snapshot.previous_low_time),
                    "previousLowPrice": to_decimal_string(snapshot.previous_low_price) if snapshot.previous_low_price is not None else None,
                    "buyTime": self._format_hms(snapshot.buy_time),
                    "buyPrice": to_decimal_string(snapshot.buy_price) if snapshot.buy_price is not None else None,
                    "previousHighTime": self._format_hms(snapshot.previous_high_time),
                    "previousHighPrice": to_decimal_string(snapshot.previous_high_price)
                    if snapshot.previous_high_price is not None
                    else None,
                    "sellTime": self._format_hms(snapshot.sell_time),
                    "sellPrice": to_decimal_string(snapshot.sell_price) if snapshot.sell_price is not None else None,
                    "currentPriceAtClose": to_decimal_string(snapshot.current_price_at_close)
                    if snapshot.current_price_at_close is not None
                    else None,
                }
            )
        return rows

    @staticmethod
    def _format_hms(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.strftime("%H:%M:%S")


def map_csm_error(error: CsmValidationError) -> tuple[int, str]:
    if error.code == "CSM_MODE_SWITCH_PRECONDITION_FAILED":
        return 409, "모드 전환 선행조건이 충족되지 않았습니다."
    return 400, "입력값 검증에 실패했습니다."


def to_decimal_string(value: Decimal) -> str:
    return format(value, "f")