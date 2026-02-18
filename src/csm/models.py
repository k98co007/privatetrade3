from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Mode = Literal["mock", "live"]


@dataclass(frozen=True)
class CsmCredential:
    app_key: str
    app_secret: str
    account_no: str
    user_id: str


@dataclass(frozen=True)
class CsmSettings:
    watch_symbols: list[str]
    mode: Mode
    live_mode_confirmed: bool


@dataclass(frozen=True)
class TradingGuardStatus:
    open_orders: int
    open_positions: int
    engine_state: str
