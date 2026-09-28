"""Instagram cookie/session persistence helpers.

These helpers keep the authenticated session available to the running
instance. Secrets are never logged.
"""

import json
import os
from pathlib import Path
from typing import Optional

from config import COOKIES_FILE

COOKIE_DIR = Path(COOKIES_FILE).parent
RAW_JSON_COOKIES = COOKIE_DIR / "instagram_raw.json"
INSTAGRAM_SETTINGS_FILE = COOKIE_DIR / "instagrapi_settings.json"


def _cookie_rows(client):
    """Extract cookies from an instagrapi client without logging values."""
    rows = []
    seen = set()

    for session_name in ("private", "public"):
        session = getattr(client, session_name, None)
        jar = getattr(session, "cookies", None)
        if jar is None:
            continue

        for cookie in jar:
            key = (
                cookie.domain,
                cookie.path,
                cookie.name,
                cookie.value,
            )
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "domain": cookie.domain or ".instagram.com",
                    "path": cookie.path or "/",
                    "secure": bool(cookie.secure),
                    "expires": int(cookie.expires or 0),
                    "name": cookie.name,
                    "value": cookie.value,
                }
            )

    return rows


def save_instagram_client_state(client) -> bool:
    """Persist the current instagrapi session and cookies to disk."""
    try:
        COOKIE_DIR.mkdir(parents=True, exist_ok=True)
        cookies = _cookie_rows(client)

        if not cookies:
            raise RuntimeError("Instagram login returned no cookies")

        with RAW_JSON_COOKIES.open("w", encoding="utf-8") as file:
            json.dump(cookies, file, indent=2)

        with Path(COOKIES_FILE).open("w", encoding="utf-8") as file:
            file.write("# Netscape HTTP Cookie File\n")
            for cookie in cookies:
                domain = cookie["domain"]
                flag = "TRUE" if domain.startswith(".") else "FALSE"
                file.write(
                    f'{domain}\t{flag}\t{cookie["path"]}\t'
                    f'{str(cookie["secure"]).upper()}\t{cookie["expires"]}\t'
                    f'{cookie["name"]}\t{cookie["value"]}\n'
                )

        # instagrapi settings contain session/device state useful for the
        # next login in the same persistent filesystem.
        try:
            client.dump_settings(str(INSTAGRAM_SETTINGS_FILE))
        except Exception:
            # Cookie files remain usable even if settings serialization changes
            # between instagrapi releases.
            pass

        os.chmod(COOKIES_FILE, 0o600)
        os.chmod(RAW_JSON_COOKIES, 0o600)
        if INSTAGRAM_SETTINGS_FILE.exists():
            os.chmod(INSTAGRAM_SETTINGS_FILE, 0o600)

        return True

    except Exception:
        return False


def get_saved_instagram_sessionid() -> Optional[str]:
    """Read sessionid from the saved Netscape cookie file."""
    cookie_file = Path(COOKIES_FILE)
    if not cookie_file.is_file():
        return None

    try:
        import http.cookiejar

        jar = http.cookiejar.MozillaCookieJar(str(cookie_file))
        jar.load(ignore_discard=True, ignore_expires=True)

        for cookie in jar:
            if cookie.name == "sessionid" and cookie.value:
                return cookie.value.strip()

    except Exception:
        return None

    return None
