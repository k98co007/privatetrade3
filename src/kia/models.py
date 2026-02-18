from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from .contracts import Mode

HttpMethod = Literal["GET", "POST"]
TransportProtocol = Literal["REST", "WEBSOCKET"]


@dataclass(frozen=True)
class EndpointInfo:
    base_url: str
    path: str
    method: HttpMethod
    protocol: TransportProtocol = "REST"


@dataclass(frozen=True)
class AccessToken:
    token: str
    issued_at: datetime
    expires_at: datetime
    refresh_at: datetime
    mode: Mode
