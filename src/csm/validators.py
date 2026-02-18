from __future__ import annotations

import re

from .errors import (
    CsmCredentialRequiredFieldMissingError,
    CsmLiveConfirmRequiredError,
    CsmModeInvalidError,
    CsmModeSwitchPreconditionFailedError,
    CsmSymbolCountOutOfRangeError,
    CsmSymbolDuplicatedError,
    CsmSymbolFormatInvalidError,
)

SYMBOL_PATTERN = re.compile(r"^[0-9]{6}$")


def normalize_symbols(watch_symbols: list[str]) -> list[str]:
    return [symbol.strip() for symbol in watch_symbols]


def validate_watch_symbols(watch_symbols: list[str]) -> None:
    if len(watch_symbols) < 1 or len(watch_symbols) > 20:
        raise CsmSymbolCountOutOfRangeError(field="watchSymbols", value=len(watch_symbols))
    if any((not symbol) or (not SYMBOL_PATTERN.match(symbol)) for symbol in watch_symbols):
        raise CsmSymbolFormatInvalidError(field="watchSymbols", value=watch_symbols)
    if len(set(watch_symbols)) != len(watch_symbols):
        raise CsmSymbolDuplicatedError(field="watchSymbols", value=watch_symbols)


def validate_mode(mode: str, live_mode_confirmed: bool) -> None:
    if mode not in ("mock", "live"):
        raise CsmModeInvalidError(field="mode", value=mode)
    if mode == "live" and live_mode_confirmed is not True:
        raise CsmLiveConfirmRequiredError(field="liveModeConfirmed", value=live_mode_confirmed)


def normalize_credential(credential: dict[str, str]) -> dict[str, str]:
    account_no = credential.get("accountNo", "").replace("-", "").strip()
    return {
        "appKey": credential.get("appKey", "").strip(),
        "appSecret": credential.get("appSecret", "").strip(),
        "accountNo": account_no,
        "userId": credential.get("userId", "").strip(),
    }


def validate_credential(credential: dict[str, str]) -> None:
    required = ("appKey", "appSecret", "accountNo", "userId")
    for key in required:
        if not credential.get(key):
            raise CsmCredentialRequiredFieldMissingError(field=key, value="")
    if not credential["accountNo"].isdigit():
        raise CsmCredentialRequiredFieldMissingError(field="accountNo", value="not-numeric")


def validate_mode_switch_guard(guard: dict[str, object]) -> None:
    open_orders = int(guard.get("openOrders", 0))
    open_positions = int(guard.get("openPositions", 0))
    engine_state = str(guard.get("engineState", ""))

    if open_orders != 0 or open_positions != 0 or engine_state != "IDLE":
        raise CsmModeSwitchPreconditionFailedError(
            field="guard",
            value={
                "openOrders": open_orders,
                "openPositions": open_positions,
                "engineState": engine_state,
            },
        )
