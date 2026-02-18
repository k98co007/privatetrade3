from __future__ import annotations

import json
from socket import timeout as socket_timeout
from typing import Any
from urllib.error import URLError

from .errors import KiaError, make_kia_error


def map_http_status(status_code: int, body: dict[str, Any] | None = None) -> KiaError:
    details = {"status": status_code, "body": body or {}}
    if status_code == 401:
        return make_kia_error("KIA_AUTH_TOKEN_EXPIRED", "인증 토큰이 만료되었습니다.", True, details)
    if status_code == 403:
        return make_kia_error("KIA_AUTH_FORBIDDEN", "API 권한이 없습니다.", False, details)
    if status_code == 404:
        return make_kia_error("KIA_QUOTE_SYMBOL_NOT_FOUND", "요청한 종목 또는 리소스를 찾을 수 없습니다.", False, details)
    if status_code == 409:
        return make_kia_error("KIA_ORDER_DUPLICATED", "동일 멱등키의 주문이 이미 처리되었습니다.", False, details)
    if status_code == 429:
        return make_kia_error("KIA_RATE_LIMITED", "호출 한도를 초과했습니다. 잠시 후 재시도하세요.", True, details)
    if 500 <= status_code <= 599:
        return make_kia_error("KIA_UPSTREAM_UNAVAILABLE", "외부 거래 API가 일시적으로 불안정합니다.", True, details)
    return make_kia_error("KIA_UNKNOWN", "알 수 없는 오류가 발생했습니다.", False, details)


def map_exception(exc: Exception) -> KiaError:
    if isinstance(exc, KiaError):
        return exc
    if isinstance(exc, (TimeoutError, socket_timeout, URLError)):
        return make_kia_error("KIA_API_TIMEOUT", "거래 API 응답 시간이 초과되었습니다.", True, {"error": str(exc)})
    if isinstance(exc, (ValueError, json.JSONDecodeError)):
        return make_kia_error("KIA_RESPONSE_INVALID", "거래 API 응답 형식이 올바르지 않습니다.", False, {"error": str(exc)})
    return make_kia_error("KIA_UNKNOWN", "알 수 없는 오류가 발생했습니다.", False, {"error": str(exc)})
