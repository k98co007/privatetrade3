from __future__ import annotations

import json
import os
import tempfile


def _atomic_write_json(path: str, payload: dict) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


class CsmRuntimeRepository:
    def __init__(
        self,
        settings_path: str = "runtime/config/settings.local.json",
        credentials_path: str = "runtime/config/credentials.local.json",
    ) -> None:
        self.settings_path = settings_path
        self.credentials_path = credentials_path

    def read_settings(self) -> dict:
        with open(self.settings_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def write_settings(self, snapshot: dict) -> None:
        _atomic_write_json(self.settings_path, snapshot)

    def read_credentials(self) -> dict:
        with open(self.credentials_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def write_credentials(self, credential_payload: dict) -> None:
        _atomic_write_json(self.credentials_path, credential_payload)
