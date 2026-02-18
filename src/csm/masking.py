from __future__ import annotations


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
