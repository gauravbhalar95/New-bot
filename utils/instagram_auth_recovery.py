"""Instagram login/challenge recovery helpers.

These helpers detect expired sessions, CSRF failures, and Instagram security
challenges. They never collect passwords or attempt to bypass verification.
"""

import os
import time
import webbrowser

INSTAGRAM_LOGIN_URL = "https://www.instagram.com/accounts/login/"
INSTAGRAM_CHALLENGE_URL = "https://www.instagram.com/challenge/"
_INSTAGRAM_AUTH_OPENED_AT = 0.0
_AUTH_COOLDOWN_SECONDS = 300


def get_instagram_login_url() -> str:
    return (
        os.getenv("INSTAGRAM_LOGIN_URL", INSTAGRAM_LOGIN_URL).strip()
        or INSTAGRAM_LOGIN_URL
    )


def get_instagram_challenge_url() -> str:
    return (
        os.getenv("INSTAGRAM_CHALLENGE_URL", INSTAGRAM_CHALLENGE_URL).strip()
        or INSTAGRAM_CHALLENGE_URL
    )


def open_instagram_login_page(force: bool = False) -> bool:
    """Open Instagram login locally, if a browser is available."""
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
    """Recognize common Instagram authentication and CSRF/challenge errors."""
    text = str(error or "").lower()
    markers = (
        "rd_challenge",
        "challenge_required",
        "checkpoint_required",
        "login_required",
        "login required",
        "csrf token",
        "csrftoken",
        "csrfmiddlewaretoken",
        "missing csrf",
        "invalid csrf",
        "csrf validation failed",
        "401",
        "403",
        "429",
        "unauthorized",
        "forbidden",
        "two-factor",
        "two factor",
        "verification code",
        "checkpoint",
        "/challenge/",
        "accounts/login",
        "this content is unreachable",
        "use --cookies-from-browser",
        "use --cookies",
    )
    return any(marker in text for marker in markers)


def build_instagram_auth_message(browser_opened: bool = False) -> str:
    login_url = get_instagram_login_url()
    challenge_url = get_instagram_challenge_url()
    browser_line = (
        "🌐 Instagram login page was opened on the bot device.\n"
        if browser_opened
        else
        "🌐 Open Instagram on your trusted phone/PC and complete any login, "
        "2FA, or security-check prompt.\n"
    )
    return (
        "🔐 <b>Instagram authorization/checkpoint required</b>\n\n"
        f"{browser_line}"
        f'🔗 <a href="{login_url}">Open Instagram Login</a>\n'
        f'🛡️ <a href="{challenge_url}">Open Instagram Challenge</a>\n\n'
        "After completing verification, create/export a fresh session cookie "
        "from your own trusted browser and update the server's "
        "INSTAGRAM_SESSIONID secret (or the configured cookie file), then "
        "restart the service and retry. A cloud server cannot read cookies "
        "from your phone browser automatically.\n\n"
        "CSRF tokens must match the authenticated session. The downloader "
        "should use the csrftoken from the same cookie jar; adding a random "
        "token or retrying a blocked challenge will not fix authentication. "
        "Never send your password or session cookies to the bot."
    )
