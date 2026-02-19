from __future__ import annotations

from typing import Any

from .contracts import Mode, ServiceType
from .errors import make_kia_error
from .models import EndpointInfo


class CsmEndpointResolver:
    ROUTES: dict[ServiceType, tuple[str, str]] = {
        "auth": ("POST", "/oauth2/token"),
        "quote": ("POST", "/api/dostk/mrkcond"),
        "chart": ("POST", "/api/dostk/chart"),
        "order": ("POST", "/api/dostk/ordr"),
        "execution": ("POST", "/api/dostk/websocket"),
    }

    def __init__(
        self,
        csm_repository: Any | None = None,
        *,
        default_mock_base_url: str = "https://mockapi.kiwoom.com",
        default_live_base_url: str = "https://api.kiwoom.com",
    ) -> None:
        self._csm_repository = csm_repository
        self._default_mock_base_url = default_mock_base_url
        self._default_live_base_url = default_live_base_url

    def resolve(self, mode: Mode, service_type: ServiceType) -> EndpointInfo:
        route = self.ROUTES.get(service_type)
        if route is None:
            raise make_kia_error("KIA_ROUTE_NOT_FOUND", "라우팅 설정을 찾을 수 없습니다.", False)
        method, path = route
        return EndpointInfo(base_url=self._resolve_base_url(mode), path=path, method=method, protocol="REST")  # type: ignore[arg-type]

    def read_csm_mode(self) -> Mode:
        if self._csm_repository is None:
            return "mock"
        try:
            settings = self._csm_repository.read_settings()
        except FileNotFoundError:
            return "mock"
        mode = str(settings.get("mode", "mock")).lower()
        if mode not in {"mock", "live"}:
            return "mock"
        return mode  # type: ignore[return-value]

    def has_live_credentials(self) -> bool:
        credential = self._read_credential()
        app_key = str(credential.get("appKey", "")).strip()
        app_secret = str(credential.get("appSecret", "")).strip()
        return bool(app_key and app_secret)

    def read_auth_payload(self) -> dict[str, str]:
        credential = self._read_credential()
        return {
            "appkey": str(credential.get("appKey", "")),
            "secretkey": str(credential.get("appSecret", "")),
        }

    def _read_credential(self) -> dict[str, Any]:
        if self._csm_repository is None:
            return {}
        try:
            payload = self._csm_repository.read_credentials()
        except FileNotFoundError:
            return {}
        if isinstance(payload.get("credential"), dict):
            return payload["credential"]
        return payload if isinstance(payload, dict) else {}

    def _resolve_base_url(self, mode: Mode) -> str:
        credential = self._read_credential()
        if mode == "mock":
            return (
                str(credential.get("mockBaseUrl") or "").strip()
                or str(credential.get("mock_base_url") or "").strip()
                or self._default_mock_base_url
            )
        return (
            str(credential.get("liveBaseUrl") or "").strip()
            or str(credential.get("live_base_url") or "").strip()
            or self._default_live_base_url
        )

