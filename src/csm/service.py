from __future__ import annotations

from datetime import datetime, timezone

from .masking import to_masked_credential
from .validators import (
    normalize_credential,
    normalize_symbols,
    validate_credential,
    validate_mode,
    validate_mode_switch_guard,
    validate_watch_symbols,
)


class CsmService:
    def __init__(self, repository) -> None:
        self.repository = repository

    def save_settings(self, request: dict) -> dict:
        watch_symbols = normalize_symbols(request["watchSymbols"])
        validate_watch_symbols(watch_symbols)

        mode = request["mode"]
        live_mode_confirmed = request["liveModeConfirmed"]
        validate_mode(mode, live_mode_confirmed)

        credential = normalize_credential(request["credential"])
        validate_credential(credential)

        raw_buy_budget = request.get("buyBudget")
        buy_budget: str | None = None
        if raw_buy_budget is not None:
            text = str(raw_buy_budget).strip().replace(",", "")
            if text:
                buy_budget = text

        now = datetime.now(timezone.utc).isoformat()
        credentials_id = f"cred-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        settings = {
            "version": "v0.1.0",
            "updatedAt": now,
            "watchSymbols": watch_symbols,
            "mode": mode,
            "liveModeConfirmed": live_mode_confirmed,
            "credentialsRef": credentials_id,
            "buyBudget": buy_budget,
        }
        credentials = {
            "credentialsId": credentials_id,
            "updatedAt": now,
            "provider": "kiwoom-rest",
            "credential": credential,
        }

        self.repository.write_credentials(credentials)
        self.repository.write_settings(settings)

        return {
            "configVersion": settings["version"],
            "updatedAt": settings["updatedAt"],
            "watchSymbols": settings["watchSymbols"],
            "mode": settings["mode"],
            "liveModeConfirmed": settings["liveModeConfirmed"],
            "buyBudget": settings.get("buyBudget"),
            "credentialMasked": to_masked_credential(credential),
        }

    def switch_mode(self, target_mode: str, live_mode_confirmed: bool, guard: dict[str, object]) -> dict:
        validate_mode(target_mode, live_mode_confirmed)
        validate_mode_switch_guard(guard)

        settings = self.repository.read_settings()
        settings["mode"] = target_mode
        settings["liveModeConfirmed"] = live_mode_confirmed
        settings["updatedAt"] = datetime.now(timezone.utc).isoformat()
        self.repository.write_settings(settings)

        return {
            "mode": settings["mode"],
            "updatedAt": settings["updatedAt"],
        }
