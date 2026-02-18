# ILD-CSM v0.1.0

- 문서명: CSM 모듈 구현 상세 설계서 (ILD)
- 버전: v0.1.0
- 작성일: 2026-02-17
- 기반 문서:
  - `docs/lld/LLD-CSM-v0.1.0.md`
  - `docs/hld/HLD-v0.1.0.md`
  - `docs/srs/SRS-v0.1.0.md`
- 모듈: `CSM` (Configuration & Secret Manager)

## 1. 구현 범위

본 문서는 LLD-CSM을 Python 구현 단위로 구체화한다.

- 설정/시크릿 저장 및 조회
- 검증(심볼/모드/자격정보)
- 암복호화 및 안전 저장 흐름
- 민감정보 마스킹 유틸
- 모드 전환 가드 체크
- UAG/KIA/OPM 연동 계약

비범위:
- 전략 실행 로직
- 주문 생성/체결 처리

## 2. 디렉터리 및 모듈 구조

```text
src/
  csm/
    __init__.py
    models.py
    schemas.py
    validators.py
    masking.py
    errors.py
    crypto/
      __init__.py
      provider.py
      aesgcm_cipher.py
      keyring.py
      keyring_windows_dpapi.py
    storage/
      __init__.py
      atomic_writer.py
      file_repository.py
    services/
      __init__.py
      config_service.py
      mode_service.py
      integration_gateway.py
    contracts.py

runtime/
  config/settings.local.json
  secrets/credentials.local.enc.json
```

## 3. Python 데이터 모델 상세

## 3.1 도메인 모델 (`models.py`)

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Mode = Literal["mock", "live"]

@dataclass(frozen=True)
class KiwoomCredential:
    app_key: str
    app_secret: str
    account_no: str
    user_id: str

@dataclass(frozen=True)
class CredentialEnvelope:
    credential_id: str
    created_at: datetime
    updated_at: datetime
    provider: str
    key_id: str
    cipher: str
    nonce_b64: str
    ciphertext_b64: str
    tag_b64: str

@dataclass(frozen=True)
class ConfigSnapshot:
    version: str
    updated_at: datetime
    watch_symbols: list[str]
    mode: Mode
    live_mode_confirmed: bool
    credentials_ref: str

@dataclass(frozen=True)
class TradingGuardStatus:
    open_orders: int
    open_positions: int
    engine_state: Literal["IDLE", "RUNNING", "STOPPING"]

@dataclass(frozen=True)
class RuntimeResolvedConfigMasked:
    watch_symbols: list[str]
    mode: Mode
    live_mode_confirmed: bool
    credential_masked: dict[str, str]
```

## 3.2 DTO/응답 모델 (`contracts.py`)

```python
from dataclasses import dataclass
from typing import Literal

Mode = Literal["mock", "live"]

@dataclass(frozen=True)
class SaveSettingsRequest:
    watch_symbols: list[str]
    mode: Mode
    live_mode_confirmed: bool
    credential: dict[str, str]

@dataclass(frozen=True)
class SaveSettingsResponse:
    config_version: str
    updated_at: str
    watch_symbols: list[str]
    mode: Mode
    live_mode_confirmed: bool
    credential_masked: dict[str, str]

@dataclass(frozen=True)
class SwitchModeRequest:
    target_mode: Mode
    live_mode_confirmed: bool

@dataclass(frozen=True)
class SwitchModeResponse:
    mode: Mode
    updated_at: str

@dataclass(frozen=True)
class ResolveKiwoomCredentialResponse:
    mode: Mode
    base_url: str
    credential: dict[str, str]
```

## 4. 설정 파일 스키마

## 4.1 `runtime/config/settings.local.json` 스키마

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CsmConfigSnapshot",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "version",
    "updatedAt",
    "watchSymbols",
    "mode",
    "liveModeConfirmed",
    "credentialsRef"
  ],
  "properties": {
    "version": {
      "type": "string",
      "const": "v0.1.0"
    },
    "updatedAt": {
      "type": "string",
      "format": "date-time"
    },
    "watchSymbols": {
      "type": "array",
      "minItems": 1,
      "maxItems": 20,
      "uniqueItems": true,
      "items": {
        "type": "string",
        "pattern": "^[0-9]{6}$"
      }
    },
    "mode": {
      "type": "string",
      "enum": ["mock", "live"]
    },
    "liveModeConfirmed": {
      "type": "boolean"
    },
    "credentialsRef": {
      "type": "string",
      "minLength": 1
    }
  },
  "allOf": [
    {
      "if": {
        "properties": { "mode": { "const": "live" } }
      },
      "then": {
        "properties": { "liveModeConfirmed": { "const": true } }
      }
    }
  ]
}
```

## 4.2 `runtime/secrets/credentials.local.enc.json` 스키마

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CredentialEnvelope",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "credentialId",
    "createdAt",
    "updatedAt",
    "provider",
    "keyId",
    "cipher",
    "nonce",
    "ciphertext",
    "tag"
  ],
  "properties": {
    "credentialId": { "type": "string", "minLength": 1 },
    "createdAt": { "type": "string", "format": "date-time" },
    "updatedAt": { "type": "string", "format": "date-time" },
    "provider": { "type": "string", "const": "kiwoom-rest" },
    "keyId": { "type": "string", "minLength": 1 },
    "cipher": { "type": "string", "const": "AES-256-GCM" },
    "nonce": { "type": "string", "pattern": "^base64:.+" },
    "ciphertext": { "type": "string", "pattern": "^base64:.+" },
    "tag": { "type": "string", "pattern": "^base64:.+" }
  }
}
```

## 5. 클래스/함수 설계

## 5.1 검증기 (`validators.py`)

```python
import re
from .errors import (
    CsmSymbolCountOutOfRangeError,
    CsmSymbolFormatInvalidError,
    CsmSymbolDuplicatedError,
    CsmModeInvalidError,
    CsmLiveConfirmRequiredError,
    CsmCredentialRequiredFieldMissingError,
)

SYMBOL_PATTERN = re.compile(r"^[0-9]{6}$")


def normalize_symbols(watch_symbols: list[str]) -> list[str]:
    return [s.strip() for s in watch_symbols]


def validate_watch_symbols(watch_symbols: list[str]) -> None:
    if len(watch_symbols) < 1 or len(watch_symbols) > 20:
        raise CsmSymbolCountOutOfRangeError(field="watchSymbols", value=len(watch_symbols))
    if any(not s or not SYMBOL_PATTERN.match(s) for s in watch_symbols):
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
    if len(credential["appKey"]) < 16 or len(credential["appSecret"]) < 16 or len(credential["userId"]) < 3:
        raise CsmCredentialRequiredFieldMissingError(field="credential", value="min-length")
```

## 5.2 마스킹 유틸 (`masking.py`)

```python
def mask_app_key(_: str) -> str:
    return "***masked***"


def mask_app_secret(_: str) -> str:
    return "***masked***"


def mask_account_no(account_no: str) -> str:
    suffix = account_no[-4:] if len(account_no) >= 4 else account_no
    return f"******{suffix}"


def mask_user_id(user_id: str) -> str:
    prefix = user_id[:2] if len(user_id) >= 2 else user_id
    return f"{prefix}***"


def to_masked_credential(credential: dict[str, str]) -> dict[str, str]:
    return {
        "appKey": mask_app_key(credential["appKey"]),
        "appSecret": mask_app_secret(credential["appSecret"]),
        "accountNo": mask_account_no(credential["accountNo"]),
        "userId": mask_user_id(credential["userId"]),
    }
```

## 5.3 암호화 계층 (`crypto/provider.py`, `crypto/aesgcm_cipher.py`)

```python
from typing import Protocol


class CipherProvider(Protocol):
    def encrypt(self, plaintext: bytes, key: bytes) -> tuple[bytes, bytes, bytes]:
        ...

    def decrypt(self, nonce: bytes, ciphertext: bytes, tag: bytes, key: bytes) -> bytes:
        ...
```

```python
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class AesGcmCipher:
    def encrypt(self, plaintext: bytes, key: bytes) -> tuple[bytes, bytes, bytes]:
        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        sealed = aesgcm.encrypt(nonce, plaintext, None)
        ciphertext, tag = sealed[:-16], sealed[-16:]
        return nonce, ciphertext, tag

    def decrypt(self, nonce: bytes, ciphertext: bytes, tag: bytes, key: bytes) -> bytes:
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext + tag, None)
```

## 5.4 키 저장소 어댑터 (`crypto/keyring.py`, `crypto/keyring_windows_dpapi.py`)

```python
from typing import Protocol


class MasterKeyProvider(Protocol):
    def get_or_create_master_key(self, key_id: str) -> bytes:
        ...
```

```python
import os
import win32crypt


class WindowsDpapiMasterKeyProvider:
    def __init__(self, path: str):
        self.path = path

    def get_or_create_master_key(self, key_id: str) -> bytes:
        os.makedirs(self.path, exist_ok=True)
        key_file = os.path.join(self.path, f"{key_id}.bin")
        if os.path.exists(key_file):
            encrypted_blob = open(key_file, "rb").read()
            return win32crypt.CryptUnprotectData(encrypted_blob, None, None, None, 0)[1]
        key = os.urandom(32)
        encrypted_blob = win32crypt.CryptProtectData(key, key_id, None, None, None, 0)
        with open(key_file, "wb") as fp:
            fp.write(encrypted_blob)
        return key
```

## 5.5 파일 저장소/원자적 쓰기 (`storage/atomic_writer.py`, `storage/file_repository.py`)

```python
import json
import os
import tempfile


def atomic_write_json(path: str, payload: dict) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
```

```python
import json
from .atomic_writer import atomic_write_json


class CsmFileRepository:
    def __init__(self, settings_path: str, secret_path: str):
        self.settings_path = settings_path
        self.secret_path = secret_path

    def read_settings(self) -> dict:
        with open(self.settings_path, "r", encoding="utf-8") as fp:
            return json.load(fp)

    def write_settings(self, snapshot: dict) -> None:
        atomic_write_json(self.settings_path, snapshot)

    def read_secret_envelope(self) -> dict:
        with open(self.secret_path, "r", encoding="utf-8") as fp:
            return json.load(fp)

    def write_secret_envelope(self, envelope: dict) -> None:
        atomic_write_json(self.secret_path, envelope)
```

## 5.6 서비스 계층 (`services/config_service.py`)

```python
from datetime import datetime, timezone
import json
import base64

from csm.masking import to_masked_credential
from csm.validators import (
    normalize_symbols,
    validate_watch_symbols,
    validate_mode,
    normalize_credential,
    validate_credential,
)


class ConfigService:
    def __init__(self, repo, cipher, key_provider, key_id: str = "csm-master-key-v1"):
        self.repo = repo
        self.cipher = cipher
        self.key_provider = key_provider
        self.key_id = key_id

    def save_settings(self, req: dict) -> dict:
        symbols = normalize_symbols(req["watchSymbols"])
        validate_watch_symbols(symbols)

        mode = req["mode"]
        live_confirmed = req["liveModeConfirmed"]
        validate_mode(mode, live_confirmed)

        credential = normalize_credential(req["credential"])
        validate_credential(credential)

        key = self.key_provider.get_or_create_master_key(self.key_id)
        plaintext = json.dumps(credential, ensure_ascii=False).encode("utf-8")
        nonce, ciphertext, tag = self.cipher.encrypt(plaintext, key)

        now = datetime.now(timezone.utc).isoformat()
        credential_id = f"cred-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        envelope = {
            "credentialId": credential_id,
            "createdAt": now,
            "updatedAt": now,
            "provider": "kiwoom-rest",
            "keyId": self.key_id,
            "cipher": "AES-256-GCM",
            "nonce": "base64:" + base64.b64encode(nonce).decode(),
            "ciphertext": "base64:" + base64.b64encode(ciphertext).decode(),
            "tag": "base64:" + base64.b64encode(tag).decode(),
        }

        snapshot = {
            "version": "v0.1.0",
            "updatedAt": now,
            "watchSymbols": symbols,
            "mode": mode,
            "liveModeConfirmed": live_confirmed,
            "credentialsRef": credential_id,
        }

        self.repo.write_secret_envelope(envelope)
        self.repo.write_settings(snapshot)

        return {
            "configVersion": snapshot["version"],
            "updatedAt": snapshot["updatedAt"],
            "watchSymbols": snapshot["watchSymbols"],
            "mode": snapshot["mode"],
            "liveModeConfirmed": snapshot["liveModeConfirmed"],
            "credentialMasked": to_masked_credential(credential),
        }
```

## 5.7 모드 전환 서비스 (`services/mode_service.py`)

```python
from datetime import datetime, timezone

from csm.validators import validate_mode, validate_credential
from csm.errors import CsmModeSwitchPreconditionFailedError


class ModeService:
    def __init__(self, repo, opm_gateway, kia_gateway, credential_loader):
        self.repo = repo
        self.opm_gateway = opm_gateway
        self.kia_gateway = kia_gateway
        self.credential_loader = credential_loader

    def switch_mode(self, target_mode: str, live_mode_confirmed: bool) -> dict:
        validate_mode(target_mode, live_mode_confirmed)

        guard = self.opm_gateway.get_trading_guard_status()
        self._check_guard(guard)

        if target_mode == "live":
            credential = self.credential_loader.load_plain_credential()
            validate_credential(credential)

        snapshot = self.repo.read_settings()
        snapshot["mode"] = target_mode
        snapshot["liveModeConfirmed"] = live_mode_confirmed
        snapshot["updatedAt"] = datetime.now(timezone.utc).isoformat()
        self.repo.write_settings(snapshot)

        self.kia_gateway.notify_mode_changed(target_mode)

        return {
            "mode": target_mode,
            "updatedAt": snapshot["updatedAt"],
        }

    @staticmethod
    def _check_guard(guard: dict) -> None:
        if guard["openOrders"] != 0 or guard["openPositions"] != 0 or guard["engineState"] != "IDLE":
            raise CsmModeSwitchPreconditionFailedError(
                field="guard",
                value={
                    "openOrders": guard["openOrders"],
                    "openPositions": guard["openPositions"],
                    "engineState": guard["engineState"],
                },
            )
```

## 6. 보안 저장(secure storage) 플로우

## 6.1 저장 플로우

1) 입력 정규화/검증 수행 (`watchSymbols`, `mode`, `credential`)
2) `MasterKeyProvider.get_or_create_master_key("csm-master-key-v1")` 호출
3) 자격정보 JSON 직렬화 후 AES-256-GCM 암호화
4) `CredentialEnvelope` 구성 (`nonce/ciphertext/tag` base64)
5) `runtime/secrets/credentials.local.enc.json` 원자적 저장
6) `credentialsRef`를 포함한 `ConfigSnapshot` 저장
7) 응답은 `credentialMasked`만 반환

## 6.2 조회/복호화 플로우

1) `settings.local.json` 로드 후 `credentialsRef` 확인
2) `credentials.local.enc.json` 로드 후 레코드 식별
3) `MasterKeyProvider`로 키 확보
4) AES-256-GCM 복호화
5) 복호화 결과 `validate_credential` 재검증
6) 외부 응답/로그는 마스킹 값만 노출

## 6.3 보안 규칙

- 평문 자격정보 파일 저장 금지
- 예외/로그 문자열에 `appKey`, `appSecret`, `accountNo`, `userId` 원문 포함 금지
- 운영 로그에는 `credentialId`, `keyId`, 오류코드만 기록

## 7. 모드 전환 가드 체크 상세

## 7.1 체크 항목

- `openOrders == 0`
- `openPositions == 0`
- `engineState == "IDLE"`
- `target_mode == "live"` 인 경우:
  - `liveModeConfirmed is True`
  - 복호화 가능한 유효 자격정보 존재

## 7.2 실패 코드 매핑

- 주문/포지션/엔진상태 위반: `CSM_MODE_SWITCH_PRECONDITION_FAILED`
- Live 확인 누락: `CSM_LIVE_CONFIRM_REQUIRED`
- 자격정보 복호화 실패: `CSM_CREDENTIAL_DECRYPT_FAILED`
- 자격정보 검증 실패: `CSM_CREDENTIAL_REQUIRED_FIELD_MISSING`

## 8. 통합 계약(Integration Contracts)

## 8.1 UAG -> CSM

### `POST /settings/save`

- 요청: `SaveSettingsRequest`
- 응답: `SaveSettingsResponse` (마스킹 필드 포함)
- 오류: CSM 표준 오류 포맷 (`code`, `message`, `retryable`, `source`, `details`)

### `POST /settings/mode/switch`

- 요청: `SwitchModeRequest`
- 응답: `SwitchModeResponse`
- 가드체크 실패 시 `409` + `CSM_MODE_SWITCH_PRECONDITION_FAILED`

## 8.2 CSM -> OPM

### `get_trading_guard_status()`

```python
def get_trading_guard_status() -> dict:
    return {
      "openOrders": 0,
      "openPositions": 0,
      "engineState": "IDLE"
    }
```

- 타임아웃: 2초
- 실패 처리: 1회 재시도 후 실패 시 `CSM_MODE_SWITCH_PRECONDITION_FAILED`로 승격

## 8.3 CSM -> KIA

### `notify_mode_changed(target_mode: str)`

- 목적: KIA 내부 API 라우팅(mock/live) 동기화
- 보장: CSM 설정 저장 성공 후 호출
- 실패 처리: 즉시 1회 재시도, 최종 실패 시 `retryable=true`로 오류 반환

### `resolve_kiwoom_credential(mode: str) -> ResolveKiwoomCredentialResponse`

- 반환: `mode`, `baseUrl`, 복호화된 credential(내부 전용)
- 외부 공개 금지: UAG/로그에는 절대 평문 전달 금지

## 9. 오류 모델 구현

## 9.1 베이스 예외 (`errors.py`)

```python
class CsmError(Exception):
    code = "CSM_INTERNAL"
    retryable = False
    source = "CSM"

    def __init__(self, field: str, value):
        self.field = field
        self.value = value

    def to_payload(self) -> dict:
        return {
            "code": self.code,
            "message": self.message(),
            "retryable": self.retryable,
            "source": self.source,
            "details": {"field": self.field, "value": self.value},
        }

    def message(self) -> str:
        return "CSM 오류"
```

## 9.2 구체 예외

- `CsmSymbolCountOutOfRangeError`
- `CsmSymbolFormatInvalidError`
- `CsmSymbolDuplicatedError`
- `CsmModeInvalidError`
- `CsmLiveConfirmRequiredError`
- `CsmModeSwitchPreconditionFailedError`
- `CsmCredentialRequiredFieldMissingError`
- `CsmCredentialEncryptFailedError`
- `CsmCredentialDecryptFailedError`
- `CsmConfigWriteFailedError`
- `CsmSecretWriteFailedError`

구현 규칙:
- `message()`는 한국어 고정 문구 사용
- `details`에는 민감정보 원문 금지

## 10. 구현 순서 (주니어 개발자용)

1) `models.py`, `contracts.py`, `errors.py` 작성
2) `validators.py`, `masking.py` 작성
3) `storage/atomic_writer.py`, `storage/file_repository.py` 작성
4) `crypto/provider.py`, `crypto/aesgcm_cipher.py` 작성
5) `crypto/keyring.py`, `crypto/keyring_windows_dpapi.py` 작성
6) `services/config_service.py` 구현
7) `services/mode_service.py` 구현
8) `services/integration_gateway.py`에서 UAG/OPM/KIA 연결
9) 단위 테스트(검증/마스킹/가드체크/암복호화) 작성
10) 통합 테스트(저장->조회->모드전환) 수행

## 11. 테스트 포인트

- 심볼 개수 경계값: 0, 1, 20, 21
- 심볼 형식: 숫자 6자리 외 입력
- Live 전환 시 `liveModeConfirmed=False` 거부
- OPM 가드 위반 조합별 실패 검증
- 암호문 파일 손상 시 복호화 실패 처리
- 로그/오류 메시지에 평문 누출이 없는지 점검

## 12. 추적성 (LLD -> ILD)

| LLD 항목 | ILD 반영 위치 |
|---|---|
| 데이터 모델(2장) | 3장 Python 모델 |
| 검증 규칙(3장) | 5.1 검증기 |
| 저장 경로 정책(4장) | 2장 구조, 5.5 저장소 |
| 암호화/마스킹(5장) | 5.2, 5.3, 5.4, 6장 |
| 모드 전환 조건(6장) | 5.7, 7장 |
| 인터페이스 계약(7장) | 8장 통합 계약 |
| 오류 모델(10장) | 9장 예외 구현 |

## 13. 결론

본 ILD-CSM v0.1.0은 LLD-CSM의 규칙을 Python 구현 단위(클래스/함수/스키마/보안플로우/연동계약)로 구체화했다. 개발자는 본 문서만으로 CSM 모듈을 코드 수준에서 구현할 수 있다.
