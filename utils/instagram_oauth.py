"""Instagram Business Login OAuth helpers for the Telegram Mini App.

This uses Meta's official Instagram API with Instagram Login. It never asks
the Mini App to collect an Instagram password or browser cookie.
"""

import secrets
import time
from typing import Optional
from urllib.parse import urlencode

import requests

from config import (
    INSTAGRAM_APP_ID,
    INSTAGRAM_APP_SECRET,
    INSTAGRAM_OAUTH_SCOPES,
    INSTAGRAM_REDIRECT_URI,
)

AUTH_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
LONG_TOKEN_URL = "https://graph.instagram.com/access_token"
PROFILE_URL = "https://graph.instagram.com/me"

STATE_TTL_SECONDS = 600

_pending_states: dict[str, dict] = {}
_instagram_accounts: dict[int, dict] = {}


def _cleanup() -> None:
    cutoff = time.time() - STATE_TTL_SECONDS
    for state, item in list(_pending_states.items()):
        if item.get("created_at", 0) < cutoff:
            _pending_states.pop(state, None)


def is_configured() -> bool:
    return bool(INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET and INSTAGRAM_REDIRECT_URI)


def create_authorization_url(telegram_user_id: int) -> str:
    if not is_configured():
        raise RuntimeError(
            "Instagram OAuth is not configured. Set INSTAGRAM_APP_ID, "
            "INSTAGRAM_APP_SECRET and INSTAGRAM_REDIRECT_URI."
        )

    _cleanup()
    state = secrets.token_urlsafe(32)
    _pending_states[state] = {
        "telegram_user_id": int(telegram_user_id),
        "created_at": time.time(),
    }

    params = {
        "client_id": INSTAGRAM_APP_ID,
        "redirect_uri": INSTAGRAM_REDIRECT_URI,
        "response_type": "code",
        "scope": INSTAGRAM_OAUTH_SCOPES,
        "state": state,
        "force_reauth": "false",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def consume_state(state: str) -> Optional[int]:
    _cleanup()
    item = _pending_states.pop(state, None)
    if not item:
        return None
    return int(item["telegram_user_id"])


def _post_form(url: str, data: dict) -> dict:
    response = requests.post(url, data=data, timeout=30)
    try:
        payload = response.json()
    except ValueError:
        payload = {"error_message": response.text[:500]}

    if response.status_code >= 400:
        raise RuntimeError(
            payload.get("error_message")
            or payload.get("error")
            or f"HTTP {response.status_code}"
        )
    return payload


def exchange_code_for_token(code: str) -> dict:
    short = _post_form(
        TOKEN_URL,
        {
            "client_id": INSTAGRAM_APP_ID,
            "client_secret": INSTAGRAM_APP_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": INSTAGRAM_REDIRECT_URI,
            "code": code,
        },
    )

    short_token = short.get("access_token")
    if not short_token:
        raise RuntimeError("Instagram did not return an access token.")

    long_response = requests.get(
        LONG_TOKEN_URL,
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": INSTAGRAM_APP_SECRET,
            "access_token": short_token,
        },
        timeout=30,
    )
    try:
        long_data = long_response.json()
    except ValueError:
        long_data = {}

    if long_response.status_code >= 400 or not long_data.get("access_token"):
        raise RuntimeError(
            long_data.get("error_message")
            or long_data.get("error")
            or "Could not exchange Instagram token."
        )

    token = long_data["access_token"]
    expires_in = int(long_data.get("expires_in") or 0)
    return {
        "access_token": token,
        "expires_at": int(time.time()) + expires_in if expires_in else None,
        "expires_in": expires_in,
    }


def fetch_profile(access_token: str) -> dict:
    response = requests.get(
        PROFILE_URL,
        params={
            "fields": "user_id,username",
            "access_token": access_token,
        },
        timeout=30,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.status_code >= 400 or payload.get("error"):
        error = payload.get("error")
        message = error.get("message") if isinstance(error, dict) else payload.get("error_message")
        raise RuntimeError(message or "Could not read Instagram profile.")

    return payload


def finish_authorization(state: str, code: str) -> tuple[int, dict]:
    telegram_user_id = consume_state(state)
    if telegram_user_id is None:
        raise RuntimeError("Instagram authorization state expired or is invalid.")

    token_data = exchange_code_for_token(code)
    profile = fetch_profile(token_data["access_token"])

    account = {
        **token_data,
        "user_id": profile.get("user_id"),
        "username": profile.get("username"),
        "connected_at": int(time.time()),
    }
    _instagram_accounts[telegram_user_id] = account
    return telegram_user_id, account


def get_account(telegram_user_id: int) -> Optional[dict]:
    account = _instagram_accounts.get(int(telegram_user_id))
    if not account:
        return None

    expires_at = account.get("expires_at")
    if expires_at and expires_at <= int(time.time()):
        _instagram_accounts.pop(int(telegram_user_id), None)
        return None

    return account


def disconnect(telegram_user_id: int) -> None:
    _instagram_accounts.pop(int(telegram_user_id), None)
