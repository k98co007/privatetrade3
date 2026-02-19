from __future__ import annotations

import json
import os
import threading
import time
import logging
from datetime import date, datetime, time as dt_time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, cast

from csm.errors import CsmValidationError
from csm.masking import to_masked_credential
from csm.repository import CsmRuntimeRepository
from csm.service import CsmService
from kia.contracts import Mode, SubmitOrderRequest
from kia.gateway import DefaultKiaGateway
from opm.service import OpmService
from prp.repository import PrpRepository
from tse.constants import MIN_PROFIT_LOCK_PCT
from tse.rules import calc_drop_rate, should_enter_buy_candidate
from tse.models import PlaceBuyOrderCommand, PlaceSellOrderCommand
from tse.quote_monitoring import QuoteMonitoringConfig, QuoteMonitoringLoop
from tse.service import TseService

from .models import MonitoringSnapshot, RuntimeState


REFERENCE_CAPTURE_TIME = dt_time(hour=9, minute=3, second=0)
MARKET_CLOSE_TIME = dt_time(hour=15, minute=30, second=0)
MARKET_TIMEZONE = timezone(timedelta(hours=9))


def _to_market_time(value: datetime) -> dt_time:
    if value.tzinfo is None:
        return value.time()
    return value.astimezone(MARKET_TIMEZONE).time()


class UagService:
    def __init__(
        self,
        *,
        settings_path: str = "runtime/config/settings.local.json",
        credentials_path: str = "runtime/config/credentials.local.json",
        prp_db_path: str = "runtime/state/prp.db",
        monitoring_state_path: str = "runtime/state/uag_monitoring_state.json",
    ) -> None:
        self._logger = logging.getLogger("privatetrade.uag")
        self.repository = CsmRuntimeRepository(settings_path=settings_path, credentials_path=credentials_path)
        self.csm_service = CsmService(repository=self.repository)
        self.prp_db_path = prp_db_path
        self.monitoring_state_path = monitoring_state_path
        self.state = RuntimeState()
        self._quote_loop: QuoteMonitoringLoop | None = None
        self._quote_loop_thread: threading.Thread | None = None
        self._quote_loop_stop = threading.Event()
        self._quote_loop_lock = threading.Lock()
        self._order_gateway: DefaultKiaGateway | None = None
        self._ensure_runtime_files()
        self._restore_monitoring_state()

    def _ensure_runtime_files(self) -> None:
        os.makedirs(os.path.dirname(self.repository.settings_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.repository.credentials_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.prp_db_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.monitoring_state_path), exist_ok=True)

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
        if self.state.trading_date != date.today():
            self.state.monitoring_snapshots = {}
            self._persist_monitoring_state()
        self._logger.info(
            "Start trading requested: trading_date=%s dry_run=%s",
            self.state.trading_date.isoformat(),
            dry_run,
        )
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
        self._logger.info("Shutdown requested: stopping quote monitoring loop")
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
            mode: Mode = cast(Mode, mode_raw) if mode_raw in {"mock", "live"} else "mock"

            self._quote_loop_stop.clear()
            tse_service = TseService(trading_date=self.state.trading_date or date.today(), watch_symbols=watch_symbols)
            self._order_gateway = DefaultKiaGateway(csm_repository=self.repository)
            self._initialize_reference_prices(
                tse_service=tse_service,
                kia_gateway=self._order_gateway,
                mode=mode,
                watch_symbols=watch_symbols,
            )
            self._quote_loop = QuoteMonitoringLoop(
                tse_service=tse_service,
                kia_gateway=self._order_gateway,
                config=QuoteMonitoringConfig(mode=mode),
            )

            self._logger.info(
                "Quote loop starting: trading_date=%s mode=%s symbols=%s dry_run=%s",
                (self.state.trading_date or date.today()).isoformat(),
                mode,
                ",".join(watch_symbols),
                self.state.dry_run,
            )

            self.state.quote_loop_state = "RUNNING"
            self.state.quote_last_cycle_error = None

            self._quote_loop_thread = threading.Thread(
                target=self._quote_monitor_worker,
                name="uag-quote-monitor",
                daemon=True,
            )
            self._quote_loop_thread.start()

    def _initialize_reference_prices(
        self,
        *,
        tse_service: TseService,
        kia_gateway: DefaultKiaGateway,
        mode: Mode,
        watch_symbols: list[str],
        now_value: datetime | None = None,
    ) -> None:
        now_market = _to_market_time(now_value or datetime.now(MARKET_TIMEZONE))

        for symbol in watch_symbols:
            snapshot = self._snapshot_for_symbol(symbol)
            symbol_ctx = tse_service.ctx.symbols.get(symbol)
            if symbol_ctx is None:
                continue

            if snapshot.price_at_0903 is not None and symbol_ctx.reference_price is None:
                symbol_ctx.reference_price = snapshot.price_at_0903
                symbol_ctx.state = "TRACKING"

            if now_market < REFERENCE_CAPTURE_TIME:
                continue
            if snapshot.price_at_0903 is not None:
                continue

            try:
                reference_price = kia_gateway.fetch_reference_price_0903(mode=mode, symbol=symbol)
            except Exception:
                self._logger.exception(
                    "Failed to backfill 09:03 reference price from Kiwoom: symbol=%s mode=%s",
                    symbol,
                    mode,
                )
                continue

            if reference_price is None or reference_price <= 0:
                continue

            occurred_at = datetime.combine(
                tse_service.ctx.trading_date,
                REFERENCE_CAPTURE_TIME,
                tzinfo=MARKET_TIMEZONE,
            )
            self._set_monitoring_field(
                snapshot=snapshot,
                field_name="price_at_0903",
                value=reference_price,
                source="QUOTE_REFERENCE_BACKFILL_0903",
                occurred_at=occurred_at,
            )

            if symbol_ctx.reference_price is None:
                symbol_ctx.reference_price = reference_price
                symbol_ctx.state = "TRACKING"

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
        self._logger.info("Quote loop stopped")

    def _quote_monitor_worker(self) -> None:
        if self._quote_loop is None:
            return

        self._quote_loop.start()
        interval_seconds = self._quote_loop.poll_interval_seconds

        while not self._quote_loop_stop.is_set() and self.state.engine_state == "RUNNING":
            try:
                cycle = self._quote_loop.run_cycle()
            except Exception:
                self.state.quote_loop_state = "STOPPED"
                self.state.quote_last_cycle_error = "UAG_QUOTE_LOOP_UNEXPECTED_ERROR"
                self._logger.exception("Quote loop crashed during run_cycle")
                break

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

            should_emit_cycle_info = (
                cycle.partial
                or cycle.fetch_error is not None
                or cycle.error_count > 0
                or cycle.quote_count == 0
                or self.state.quote_last_command_count > 0
                or (self.state.quote_cycles_total % 30 == 0)
            )
            if should_emit_cycle_info:
                self._logger.info(
                    "Quote cycle summary: cycle_id=%s state=%s partial=%s quotes=%s errors=%s commands=%s events=%s fetch_error=%s",
                    cycle.poll_cycle_id,
                    cycle.state,
                    cycle.partial,
                    cycle.quote_count,
                    cycle.error_count,
                    self.state.quote_last_command_count,
                    self.state.quote_last_strategy_event_count,
                    cycle.fetch_error,
                )

            if not self.state.dry_run:
                self._execute_cycle_commands(cycle.outputs)
            elif self.state.quote_last_command_count > 0:
                self._logger.info(
                    "Dry-run active: skipping %s generated commands for cycle=%s",
                    self.state.quote_last_command_count,
                    cycle.poll_cycle_id,
                )

            if self._quote_loop_stop.is_set() or self.state.engine_state != "RUNNING":
                break
            time.sleep(interval_seconds)

    def _execute_cycle_commands(self, outputs: list) -> None:
        command_count = sum(len(output.commands) for output in outputs)
        if command_count > 0:
            self._logger.info("Executing cycle commands: count=%s", command_count)
        for output in outputs:
            for command in output.commands:
                self._execute_tse_command(command)

    def _execute_tse_command(self, command: PlaceBuyOrderCommand | PlaceSellOrderCommand) -> None:
        if self._order_gateway is None:
            self._logger.warning("Skip command execution because order gateway is not initialized")
            return

        mode, account_no = self._read_order_execution_context()
        side = "BUY" if isinstance(command, PlaceBuyOrderCommand) else "SELL"
        quantity = self._resolve_order_quantity(side=side, order_price=command.order_price)
        if quantity <= 0:
            self._logger.warning(
                "Skip command due to resolved quantity <= 0: command_id=%s symbol=%s side=%s order_price=%s",
                command.command_id,
                command.symbol,
                side,
                command.order_price,
            )
            return
        now = datetime.now().astimezone()

        self._logger.info(
            "Submitting order command: command_id=%s symbol=%s side=%s qty=%s price=%s",
            command.command_id,
            command.symbol,
            side,
            quantity,
            command.order_price,
        )

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
                self._logger.exception(
                    "Order submit failed: command_id=%s symbol=%s side=%s",
                    command.command_id,
                    command.symbol,
                    side,
                )
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
            self._logger.info(
                "Order submit completed: command_id=%s symbol=%s side=%s status=%s broker_order_id=%s",
                command.command_id,
                command.symbol,
                side,
                final_status,
                result.broker_order_id,
            )

    def _read_order_execution_context(self) -> tuple[Mode | None, str]:
        settings = self.repository.read_settings()
        mode_value = str(settings.get("mode", "mock"))
        mode: Mode | None = cast(Mode, mode_value) if mode_value in {"mock", "live"} else None

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

    def _set_monitoring_field(
        self,
        *,
        snapshot: MonitoringSnapshot,
        field_name: str,
        value: Any,
        source: str,
        occurred_at: datetime | None = None,
    ) -> None:
        before = getattr(snapshot, field_name)
        if before == value:
            return

        setattr(snapshot, field_name, value)

        if field_name in {"current_price", "current_price_at_close"}:
            return

        self._logger.info(
            "Monitor row updated: symbol=%s field=%s before=%s after=%s source=%s occurred_at=%s",
            snapshot.symbol_code,
            field_name,
            self._format_monitoring_value(before),
            self._format_monitoring_value(value),
            source,
            occurred_at.isoformat() if occurred_at else None,
        )

    @staticmethod
    def _format_monitoring_value(value: Any) -> str:
        if value is None:
            return "None"
        if isinstance(value, Decimal):
            return to_decimal_string(value)
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    def _update_monitoring_snapshots(self, cycle: Any) -> None:
        for quote in cycle.quotes:
            snapshot = self._snapshot_for_symbol(quote.symbol)
            quote_time = quote.as_of
            quote_symbol_name = str(getattr(quote, "symbol_name", "") or "").strip()
            if quote_symbol_name and quote_symbol_name != snapshot.symbol_name:
                self._set_monitoring_field(
                    snapshot=snapshot,
                    field_name="symbol_name",
                    value=quote_symbol_name,
                    source="QUOTE_METADATA",
                    occurred_at=quote_time,
                )
            market_time = _to_market_time(quote_time)
            quote_price = quote.price

            if quote_price <= 0:
                self._logger.warning(
                    "Skip non-positive quote for monitoring snapshot: symbol=%s price=%s as_of=%s cycle_id=%s",
                    quote.symbol,
                    self._format_monitoring_value(quote_price),
                    quote_time.isoformat(),
                    getattr(cycle, "poll_cycle_id", None),
                )
                continue

            if snapshot.price_at_0903 is None and market_time >= REFERENCE_CAPTURE_TIME:
                self._set_monitoring_field(
                    snapshot=snapshot,
                    field_name="price_at_0903",
                    value=quote_price,
                    source="QUOTE_REFERENCE_CAPTURE",
                    occurred_at=quote_time,
                )

            self._set_monitoring_field(
                snapshot=snapshot,
                field_name="current_price",
                value=quote_price,
                source="QUOTE_TICK",
                occurred_at=quote_time,
            )

            if snapshot.buy_time is None and (
                snapshot.previous_low_price is None or quote_price <= snapshot.previous_low_price
            ):
                self._set_monitoring_field(
                    snapshot=snapshot,
                    field_name="previous_low_price",
                    value=quote_price,
                    source="QUOTE_PREVIOUS_LOW",
                    occurred_at=quote_time,
                )
                self._set_monitoring_field(
                    snapshot=snapshot,
                    field_name="previous_low_time",
                    value=quote_time,
                    source="QUOTE_PREVIOUS_LOW",
                    occurred_at=quote_time,
                )

            if self._meets_previous_high_requirements(
                snapshot=snapshot,
                quote_time=quote_time,
                quote_price=quote_price,
            ) and (snapshot.previous_high_price is None or quote_price >= snapshot.previous_high_price):
                self._set_monitoring_field(
                    snapshot=snapshot,
                    field_name="previous_high_price",
                    value=quote_price,
                    source="QUOTE_PREVIOUS_HIGH",
                    occurred_at=quote_time,
                )
                self._set_monitoring_field(
                    snapshot=snapshot,
                    field_name="previous_high_time",
                    value=quote_time,
                    source="QUOTE_PREVIOUS_HIGH",
                    occurred_at=quote_time,
                )

            if snapshot.current_price_at_close is None and market_time >= MARKET_CLOSE_TIME:
                self._set_monitoring_field(
                    snapshot=snapshot,
                    field_name="current_price_at_close",
                    value=quote_price,
                    source="QUOTE_MARKET_CLOSE_CAPTURE",
                    occurred_at=quote_time,
                )

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
                    self._set_monitoring_field(
                        snapshot=snapshot,
                        field_name="buy_time",
                        value=buy_signal_times.get(command.symbol, datetime.now().astimezone()),
                        source="BUY_COMMAND",
                        occurred_at=buy_signal_times.get(command.symbol),
                    )
                    self._set_monitoring_field(
                        snapshot=snapshot,
                        field_name="buy_price",
                        value=command.order_price,
                        source="BUY_COMMAND",
                        occurred_at=buy_signal_times.get(command.symbol),
                    )
                    self._set_monitoring_field(
                        snapshot=snapshot,
                        field_name="previous_high_time",
                        value=None,
                        source="BUY_COMMAND_RESET_PREVIOUS_HIGH",
                        occurred_at=buy_signal_times.get(command.symbol),
                    )
                    self._set_monitoring_field(
                        snapshot=snapshot,
                        field_name="previous_high_price",
                        value=None,
                        source="BUY_COMMAND_RESET_PREVIOUS_HIGH",
                        occurred_at=buy_signal_times.get(command.symbol),
                    )
                elif isinstance(command, PlaceSellOrderCommand):
                    self._set_monitoring_field(
                        snapshot=snapshot,
                        field_name="sell_time",
                        value=sell_signal_times.get(command.symbol, datetime.now().astimezone()),
                        source="SELL_COMMAND",
                        occurred_at=sell_signal_times.get(command.symbol),
                    )
                    self._set_monitoring_field(
                        snapshot=snapshot,
                        field_name="sell_price",
                        value=command.order_price,
                        source="SELL_COMMAND",
                        occurred_at=sell_signal_times.get(command.symbol),
                    )

        self._persist_monitoring_state()

    def _restore_monitoring_state(self) -> None:
        if not os.path.exists(self.monitoring_state_path):
            return

        try:
            with open(self.monitoring_state_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            self._logger.warning("Failed to read monitoring state file: path=%s", self.monitoring_state_path)
            return

        trading_date_raw = payload.get("tradingDate")
        if not isinstance(trading_date_raw, str):
            return

        try:
            stored_trading_date = date.fromisoformat(trading_date_raw)
        except ValueError:
            self._logger.warning("Invalid tradingDate in monitoring state: tradingDate=%s", trading_date_raw)
            return

        if stored_trading_date != date.today():
            self._delete_monitoring_state_file()
            return

        snapshots_raw = payload.get("snapshots")
        if not isinstance(snapshots_raw, dict):
            return

        restored: dict[str, MonitoringSnapshot] = {}
        for symbol, raw_snapshot in snapshots_raw.items():
            if not isinstance(symbol, str) or not isinstance(raw_snapshot, dict):
                continue
            try:
                restored[symbol] = MonitoringSnapshot(
                    symbol_code=str(raw_snapshot.get("symbolCode", symbol)),
                    symbol_name=str(raw_snapshot.get("symbolName", symbol)),
                    price_at_0903=self._deserialize_decimal(raw_snapshot.get("priceAt0903")),
                    current_price=self._deserialize_decimal(raw_snapshot.get("currentPrice")),
                    current_price_at_close=self._deserialize_decimal(raw_snapshot.get("currentPriceAtClose")),
                    previous_low_time=self._deserialize_datetime(raw_snapshot.get("previousLowTime")),
                    previous_low_price=self._deserialize_decimal(raw_snapshot.get("previousLowPrice")),
                    buy_time=self._deserialize_datetime(raw_snapshot.get("buyTime")),
                    buy_price=self._deserialize_decimal(raw_snapshot.get("buyPrice")),
                    previous_high_time=self._deserialize_datetime(raw_snapshot.get("previousHighTime")),
                    previous_high_price=self._deserialize_decimal(raw_snapshot.get("previousHighPrice")),
                    sell_time=self._deserialize_datetime(raw_snapshot.get("sellTime")),
                    sell_price=self._deserialize_decimal(raw_snapshot.get("sellPrice")),
                )
            except (TypeError, ValueError, InvalidOperation):
                self._logger.warning("Skip invalid monitoring snapshot for symbol=%s", symbol)

        self.state.monitoring_snapshots = restored
        self.state.trading_date = stored_trading_date
        self._logger.info(
            "Monitoring state restored: trading_date=%s symbols=%s",
            stored_trading_date.isoformat(),
            len(restored),
        )

    def _persist_monitoring_state(self) -> None:
        trading_date_value = self.state.trading_date or date.today()
        payload = {
            "tradingDate": trading_date_value.isoformat(),
            "updatedAt": datetime.now().astimezone().isoformat(),
            "snapshots": {
                symbol: {
                    "symbolCode": snapshot.symbol_code,
                    "symbolName": snapshot.symbol_name,
                    "priceAt0903": self._serialize_decimal(snapshot.price_at_0903),
                    "currentPrice": self._serialize_decimal(snapshot.current_price),
                    "currentPriceAtClose": self._serialize_decimal(snapshot.current_price_at_close),
                    "previousLowTime": self._serialize_datetime(snapshot.previous_low_time),
                    "previousLowPrice": self._serialize_decimal(snapshot.previous_low_price),
                    "buyTime": self._serialize_datetime(snapshot.buy_time),
                    "buyPrice": self._serialize_decimal(snapshot.buy_price),
                    "previousHighTime": self._serialize_datetime(snapshot.previous_high_time),
                    "previousHighPrice": self._serialize_decimal(snapshot.previous_high_price),
                    "sellTime": self._serialize_datetime(snapshot.sell_time),
                    "sellPrice": self._serialize_decimal(snapshot.sell_price),
                }
                for symbol, snapshot in self.state.monitoring_snapshots.items()
            },
        }

        try:
            with open(self.monitoring_state_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False)
        except OSError:
            self._logger.warning("Failed to persist monitoring state file: path=%s", self.monitoring_state_path)

    def _delete_monitoring_state_file(self) -> None:
        try:
            os.remove(self.monitoring_state_path)
        except FileNotFoundError:
            return
        except OSError:
            self._logger.warning("Failed to delete stale monitoring state file: path=%s", self.monitoring_state_path)

    @staticmethod
    def _serialize_decimal(value: Decimal | None) -> str | None:
        if value is None:
            return None
        return to_decimal_string(value)

    @staticmethod
    def _deserialize_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))

    @staticmethod
    def _serialize_datetime(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    @staticmethod
    def _deserialize_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(str(value))

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

            previous_low_price = snapshot.previous_low_price
            previous_low_is_tracked = False
            if previous_low_price is not None and snapshot.price_at_0903 is not None:
                drop_rate = calc_drop_rate(snapshot.price_at_0903, previous_low_price)
                previous_low_is_tracked = should_enter_buy_candidate(drop_rate)

            if not previous_low_is_tracked:
                previous_low_price = None
            previous_low_time = snapshot.previous_low_time if previous_low_is_tracked else None

            has_previous_low_buy = snapshot.buy_time is not None and snapshot.buy_price is not None
            should_show_previous_high = previous_low_is_tracked and has_previous_low_buy
            previous_high_is_valid = (
                should_show_previous_high
                and snapshot.previous_high_time is not None
                and snapshot.previous_high_price is not None
                and self._meets_previous_high_requirements(
                    snapshot=snapshot,
                    quote_time=snapshot.previous_high_time,
                    quote_price=snapshot.previous_high_price,
                )
            )
            previous_high_price = snapshot.previous_high_price if previous_high_is_valid else None
            previous_high_time = snapshot.previous_high_time if previous_high_is_valid else None

            rows.append(
                {
                    "symbolName": snapshot.symbol_name,
                    "symbolCode": snapshot.symbol_code,
                    "priceAt0903": to_decimal_string(snapshot.price_at_0903) if snapshot.price_at_0903 is not None else None,
                    "currentPrice": to_decimal_string(current_price) if current_price is not None else None,
                    "previousLowTime": self._format_hms(previous_low_time),
                    "previousLowPrice": to_decimal_string(previous_low_price) if previous_low_price is not None else None,
                    "buyTime": self._format_hms(snapshot.buy_time),
                    "buyPrice": to_decimal_string(snapshot.buy_price) if snapshot.buy_price is not None else None,
                    "previousHighTime": self._format_hms(previous_high_time),
                    "previousHighPrice": to_decimal_string(previous_high_price)
                    if previous_high_price is not None
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
        return _to_market_time(value).strftime("%H:%M:%S")

    def _meets_previous_high_requirements(
        self,
        *,
        snapshot: MonitoringSnapshot,
        quote_time: datetime,
        quote_price: Decimal,
    ) -> bool:
        if snapshot.buy_time is None or snapshot.buy_price is None:
            return False
        if _to_market_time(quote_time) < _to_market_time(snapshot.buy_time):
            return False

        required_price = snapshot.buy_price * (Decimal("1") + (MIN_PROFIT_LOCK_PCT / Decimal("100")))
        return quote_price >= required_price


def map_csm_error(error: CsmValidationError) -> tuple[int, str]:
    if error.code == "CSM_MODE_SWITCH_PRECONDITION_FAILED":
        return 409, "모드 전환 선행조건이 충족되지 않았습니다."
    return 400, "입력값 검증에 실패했습니다."


def to_decimal_string(value: Decimal) -> str:
    return format(value, "f")