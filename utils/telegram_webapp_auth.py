"""Telegram Mini App initData validation."""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def validate_init_data(
    raw_init_data: str,
    bot_token: str,
    max_age_seconds: int = 3600,
) -> dict:
    if not raw_init_data:
        raise ValueError("Telegram initData is missing.")

    pairs = parse_qsl(raw_init_data, keep_blank_values=True)
    data = dict(pairs)
    received_hash = data.pop("hash", None)

    if not received_hash:
        raise ValueError("Telegram initData hash is missing.")

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(data.items())
    )

    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise ValueError("Telegram initData signature is invalid.")

    try:
        auth_date = int(data.get("auth_date", "0"))
    except ValueError as exc:
        raise ValueError("Telegram auth_date is invalid.") from exc

    if auth_date <= 0 or abs(time.time() - auth_date) > max_age_seconds:
        raise ValueError("Telegram initData has expired.")

    try:
        user = json.loads(data.get("user", "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError("Telegram user data is invalid.") from exc

    if not user.get("id"):
        raise ValueError("Telegram user ID is missing.")

    return user
