from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from csm.errors import (
    CsmLiveConfirmRequiredError,
    CsmModeSwitchPreconditionFailedError,
    CsmSymbolCountOutOfRangeError,
    CsmSymbolDuplicatedError,
    CsmSymbolFormatInvalidError,
)
from csm.masking import to_masked_credential
from csm.repository import CsmRuntimeRepository
from csm.service import CsmService
from csm.validators import validate_watch_symbols


def test_validate_watch_symbols_constraints() -> None:
    with pytest.raises(CsmSymbolCountOutOfRangeError):
        validate_watch_symbols([])

    with pytest.raises(CsmSymbolFormatInvalidError):
        validate_watch_symbols(["00593A"])

    with pytest.raises(CsmSymbolDuplicatedError):
        validate_watch_symbols(["005930", "005930"])

    validate_watch_symbols(["005930", "000660"])


def test_save_settings_writes_runtime_local_json_and_masks(tmp_path: Path) -> None:
    repo = CsmRuntimeRepository(
        settings_path=str(tmp_path / "runtime" / "config" / "settings.local.json"),
        credentials_path=str(tmp_path / "runtime" / "config" / "credentials.local.json"),
    )
    service = CsmService(repository=repo)

    response = service.save_settings(
        {
            "watchSymbols": [" 005930 ", "000660"],
            "mode": "mock",
            "liveModeConfirmed": False,
            "buyBudget": "1234567",
            "credential": {
                "appKey": "A" * 16,
                "appSecret": "B" * 16,
                "accountNo": "123-456-7890",
                "userId": "alpha",
            },
        }
    )

    settings_path = tmp_path / "runtime" / "config" / "settings.local.json"
    credentials_path = tmp_path / "runtime" / "config" / "credentials.local.json"

    assert settings_path.exists()
    assert credentials_path.exists()

    settings_payload = json.loads(settings_path.read_text(encoding="utf-8"))
    credentials_payload = json.loads(credentials_path.read_text(encoding="utf-8"))

    assert settings_payload["watchSymbols"] == ["005930", "000660"]
    assert settings_payload["mode"] == "mock"
    assert settings_payload["buyBudget"] == "1234567"
    assert settings_payload["credentialsRef"] == credentials_payload["credentialsId"]
    assert credentials_payload["credential"]["accountNo"] == "1234567890"

    assert response["credentialMasked"]["appKey"] == "***masked***"
    assert response["credentialMasked"]["appSecret"] == "***masked***"
    assert response["credentialMasked"]["accountNo"] == "******7890"
    assert response["credentialMasked"]["userId"] == "al***"
    assert response["buyBudget"] == "1234567"


def test_switch_mode_requires_live_confirmation_and_guard(tmp_path: Path) -> None:
    repo = CsmRuntimeRepository(
        settings_path=str(tmp_path / "runtime" / "config" / "settings.local.json"),
        credentials_path=str(tmp_path / "runtime" / "config" / "credentials.local.json"),
    )
    service = CsmService(repository=repo)

    service.save_settings(
        {
            "watchSymbols": ["005930"],
            "mode": "mock",
            "liveModeConfirmed": False,
            "credential": {
                "appKey": "A" * 16,
                "appSecret": "B" * 16,
                "accountNo": "1234567890",
                "userId": "alpha",
            },
        }
    )

    with pytest.raises(CsmLiveConfirmRequiredError):
        service.switch_mode(
            target_mode="live",
            live_mode_confirmed=False,
            guard={"openOrders": 0, "openPositions": 0, "engineState": "IDLE"},
        )

    with pytest.raises(CsmModeSwitchPreconditionFailedError):
        service.switch_mode(
            target_mode="live",
            live_mode_confirmed=True,
            guard={"openOrders": 1, "openPositions": 0, "engineState": "IDLE"},
        )

    switched = service.switch_mode(
        target_mode="live",
        live_mode_confirmed=True,
        guard={"openOrders": 0, "openPositions": 0, "engineState": "IDLE"},
    )
    assert switched["mode"] == "live"


def test_masking_utility_shape() -> None:
    masked = to_masked_credential(
        {
            "appKey": "sample-app-key",
            "appSecret": "sample-app-secret",
            "accountNo": "12345678",
            "userId": "abuser",
        }
    )

    assert set(masked.keys()) == {"appKey", "appSecret", "accountNo", "userId"}
    assert masked["appKey"] == "***masked***"
    assert masked["appSecret"] == "***masked***"
    assert masked["accountNo"] == "******5678"
    assert masked["userId"] == "ab***"
