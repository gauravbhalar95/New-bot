"""Instagram cookie/session persistence helpers.

These helpers keep the authenticated session available to the running
instance. Secrets are never logged.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from config import COOKIES_FILE

logger = logging.getLogger(__name__)

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

    except Exception as exc:
        logger.debug(f"Failed to save Instagram client state: {exc}")
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
        pass

    # Fallback: parse Netscape file lines directly
    try:
        for line in cookie_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7 and parts[5] == "sessionid" and parts[6].strip():
                return parts[6].strip()
    except Exception:
        return None

    return None


def refresh_instagram_session() -> bool:
    """Refresh or create the Instagram Netscape cookies file from saved state or env vars."""
    try:
        COOKIE_DIR.mkdir(parents=True, exist_ok=True)
        cookie_path = Path(COOKIES_FILE)

        # 1. Write directly if full Netscape cookies are provided in env
        raw_cookies = os.getenv("INSTAGRAM_COOKIES_TXT") or os.getenv("INSTAGRAM_COOKIES")
        if raw_cookies and raw_cookies.strip():
            content = raw_cookies.strip()
            if not content.startswith("# Netscape HTTP Cookie File"):
                content = "# Netscape HTTP Cookie File\n" + content
            cookie_path.write_text(content + "\n", encoding="utf-8")
            os.chmod(COOKIES_FILE, 0o600)
            logger.info("✅ Instagram cookies refreshed from INSTAGRAM_COOKIES_TXT env.")
            return True

        # 2. Gather credentials from environment or existing cookie file
        session_id = (
            os.getenv("INSTAGRAM_SESSIONID")
            or os.getenv("IG_SESSIONID")
            or get_saved_instagram_sessionid()
        )
        username = os.getenv("INSTAGRAM_USERNAME") or os.getenv("IG_USERNAME")
        password = os.getenv("INSTAGRAM_PASSWORD") or os.getenv("IG_PASSWORD")

        # 3. Attempt full session refresh via instagrapi if available
        try:
            from instagrapi import Client

            client = Client()
            if INSTAGRAM_SETTINGS_FILE.exists():
                try:
                    client.load_settings(str(INSTAGRAM_SETTINGS_FILE))
                except Exception:
                    pass

            if session_id:
                try:
                    client.login_by_sessionid(session_id.strip())
                    if save_instagram_client_state(client):
                        logger.info("✅ Instagram session refreshed via sessionid.")
                        return True
                except Exception as exc:
                    logger.debug(f"instagrapi login_by_sessionid failed: {exc}")

            if username and password:
                try:
                    client.login(username.strip(), password.strip())
                    if save_instagram_client_state(client):
                        logger.info("✅ Instagram session refreshed via username/password.")
                        return True
                except Exception as exc:
                    logger.warning(f"instagrapi username/password login failed: {exc}")
        except ImportError:
            logger.debug("instagrapi not installed; skipping client refresh.")

        # 4. Fallback: write minimal Netscape cookie file from session_id if present
        if session_id and (not cookie_path.exists() or cookie_path.stat().st_size == 0):
            cookie_path.write_text(
                "# Netscape HTTP Cookie File\n"
                f".instagram.com\tTRUE\t/\tTRUE\t2147483647\tsessionid\t{session_id.strip()}\n",
                encoding="utf-8",
            )
            os.chmod(COOKIES_FILE, 0o600)
            logger.info("✅ Minimal Instagram sessionid cookie file created.")
            return True

        # 5. Return True if an existing non-empty cookie file is already on disk
        if cookie_path.exists() and cookie_path.stat().st_size > 0:
            return True

        logger.warning("⚠️ No Instagram session/cookies configured to refresh.")
        return False

    except Exception as exc:
        logger.warning(f"⚠️ refresh_instagram_session encountered an error: {exc}")
        return False
