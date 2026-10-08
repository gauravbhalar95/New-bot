"""Instagram login/challenge recovery helpers.

This opens Instagram's normal login page on the machine running the bot.
It does not collect or transmit Instagram passwords or browser cookies.
On cloud hosts such as Koyeb, no local browser is available, so the bot
instead provides the login URL to the Telegram user.
"""

import os
import time
import webbrowser

INSTAGRAM_LOGIN_URL = "https://www.instagram.com/accounts/login/"
_INSTAGRAM_AUTH_OPENED_AT = 0.0
_AUTH_COOLDOWN_SECONDS = 300


def get_instagram_login_url() -> str:
    return os.getenv("INSTAGRAM_LOGIN_URL", INSTAGRAM_LOGIN_URL).strip() or INSTAGRAM_LOGIN_URL


def open_instagram_login_page(force: bool = False) -> bool:
    """Open Instagram login in the local browser, when a browser exists."""
    global _INSTAGRAM_AUTH_OPENED_AT

    now = time.monotonic()
    if not force and now - _INSTAGRAM_AUTH_OPENED_AT < _AUTH_COOLDOWN_SECONDS:
        return False

    _INSTAGRAM_AUTH_OPENED_AT = now

    enabled = os.getenv("OPEN_INSTAGRAM_BROWSER", "true").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        return False

    try:
        return bool(webbrowser.open(get_instagram_login_url(), new=2))
    except Exception:
        return False


def is_instagram_auth_error(error: object) -> bool:
    text = str(error or "").lower()
    markers = (
        "challenge_required",
        "checkpoint_required",
        "login_required",
        "login required",
        "401",
        "403",
        "unauthorized",
        "forbidden",
        "two-factor",
        "two factor",
        "verification code",
        "checkpoint",
        "accounts/login",
        "this content is unreachable",
        "use --cookies-from-browser",
        "use --cookies",
    )
    return any(marker in text for marker in markers)


def build_instagram_auth_message(browser_opened: bool = False) -> str:
    url = get_instagram_login_url()
    browser_line = (
        "🌐 Instagram login page was opened on the bot device.\n"
        if browser_opened
        else
        "🌐 Open the Instagram login page on your phone/PC and complete any "
        "login, 2FA, or security-check prompt.\n"
    )
    return (
        "🔐 <b>Instagram authorization required</b>\n\n"
        f"{browser_line}"
        f'🔗 <a href="{url}">Open Instagram Login</a>\n\n'
        "After completing the security check, send the Instagram media link "
        "again.\n\n"
        "⚠️ Important: logging into Instagram in your phone browser does not "
        "transfer that browser session to a Koyeb/cloud bot. The bot can only "
        "use authentication already available to the server (for example a "
        "valid INSTAGRAM_SESSIONID). Never send your Instagram password or "
        "session cookie to the bot."
    )
