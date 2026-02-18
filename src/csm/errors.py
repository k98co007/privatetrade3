from __future__ import annotations


class CsmValidationError(ValueError):
    def __init__(self, code: str, field: str, value: object) -> None:
        super().__init__(f"{code}: field={field}, value={value}")
        self.code = code
        self.field = field
        self.value = value


class CsmSymbolCountOutOfRangeError(CsmValidationError):
    def __init__(self, field: str, value: object) -> None:
        super().__init__("CSM_SYMBOL_COUNT_OUT_OF_RANGE", field, value)


class CsmSymbolFormatInvalidError(CsmValidationError):
    def __init__(self, field: str, value: object) -> None:
        super().__init__("CSM_SYMBOL_FORMAT_INVALID", field, value)


class CsmSymbolDuplicatedError(CsmValidationError):
    def __init__(self, field: str, value: object) -> None:
        super().__init__("CSM_SYMBOL_DUPLICATED", field, value)


class CsmModeInvalidError(CsmValidationError):
    def __init__(self, field: str, value: object) -> None:
        super().__init__("CSM_MODE_INVALID", field, value)


class CsmLiveConfirmRequiredError(CsmValidationError):
    def __init__(self, field: str, value: object) -> None:
        super().__init__("CSM_LIVE_CONFIRM_REQUIRED", field, value)


class CsmCredentialRequiredFieldMissingError(CsmValidationError):
    def __init__(self, field: str, value: object) -> None:
        super().__init__("CSM_CREDENTIAL_REQUIRED_FIELD_MISSING", field, value)


class CsmModeSwitchPreconditionFailedError(CsmValidationError):
    def __init__(self, field: str, value: object) -> None:
        super().__init__("CSM_MODE_SWITCH_PRECONDITION_FAILED", field, value)
