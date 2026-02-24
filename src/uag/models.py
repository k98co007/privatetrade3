from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


Mode = Literal["mock", "live"]


class CredentialInput(BaseModel):
    appKey: str = Field(min_length=1, max_length=128)
    appSecret: str = Field(min_length=1, max_length=256)
    accountNo: str = Field(min_length=8, max_length=32)
    userId: str = Field(min_length=1, max_length=64)


class SettingsSaveRequest(BaseModel):
    watchSymbols: list[str] = Field(min_length=1, max_length=20)
    mode: Mode
    liveModeConfirmed: bool
    buyBudget: str | None = None
    credential: CredentialInput


class ModeSwitchRequest(BaseModel):
    targetMode: Mode
    liveModeConfirmed: bool


class TradingStartRequest(BaseModel):
    tradingDate: date | None = None
    dryRun: bool = True


class EnvelopeMeta(BaseModel):
    timestamp: str


@dataclass
class RuntimeState:
    engine_state: Literal["IDLE", "RUNNING"] = "IDLE"
    trading_started_at: datetime | None = None
    dry_run: bool = True
    trading_date: date | None = None
    quote_loop_state: Literal["RUNNING", "DEGRADED", "STOPPED"] = "STOPPED"
    quote_cycles_total: int = 0
    quote_last_poll_cycle_id: str | None = None
    quote_last_cycle_at: datetime | None = None
    quote_last_cycle_partial: bool = False
    quote_last_quote_count: int = 0
    quote_last_error_count: int = 0
    quote_last_command_count: int = 0
    quote_last_strategy_event_count: int = 0
    quote_last_cycle_error: str | None = None
    monitoring_snapshots: dict[str, "MonitoringSnapshot"] = field(default_factory=dict)


@dataclass
class MonitoringSnapshot:
    symbol_code: str
    symbol_name: str
    price_at_0830: Decimal | None = None
    current_price: Decimal | None = None
    current_price_at_close: Decimal | None = None
    previous_low_tracking_started: bool = False
    previous_low_time: datetime | None = None
    previous_low_price: Decimal | None = None
    buy_time: datetime | None = None
    buy_price: Decimal | None = None
    previous_high_time: datetime | None = None
    previous_high_price: Decimal | None = None
    sell_time: datetime | None = None
    sell_price: Decimal | None = None


def build_success_envelope(*, request_id: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": True,
        "requestId": request_id,
        "data": data,
        "meta": {"timestamp": datetime.now().astimezone().isoformat()},
    }


def build_error_envelope(
    *,
    request_id: str,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    retryable: bool = False,
) -> dict[str, Any]:
    return {
        "success": False,
        "requestId": request_id,
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
            "source": "UAG",
            "details": details or [],
        },
        "meta": {"timestamp": datetime.now().astimezone().isoformat()},
    }