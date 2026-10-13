"""Secure YouTube cookie refresh helpers.

Cookies are credentials: never log their contents or commit the cookie file.
The URL source must be a private HTTPS endpoint controlled by the bot owner.
"""
import os
import tempfile
from pathlib import Path

import aiohttp

from config import YOUTUBE_COOKIES_URL, YOUTUBE_COOKIE_REFRESH_HOURS, YOUTUBE_FILE
from utils.logger import setup_logging

logger = setup_logging()
MAX_COOKIE_BYTES = 2 * 1024 * 1024


def validate_cookie_data(data: bytes) -> bool:
    if not data or len(data) > MAX_COOKIE_BYTES:
        return False
    text = data.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    has_header = any(
        line.strip() in {"# Netscape HTTP Cookie File", "# HTTP Cookie File"}
        for line in lines[:20]
    )
    rows = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) >= 7:
            rows.append(columns)
    if not rows:
        return False
    domains = [row[0].lower().lstrip(".") for row in rows]
    youtube_cookie = any(
        domain == "youtube.com"
        or domain.endswith(".youtube.com")
        or domain == "google.com"
        or domain.endswith(".google.com")
        or domain == "googlevideo.com"
        or domain.endswith(".googlevideo.com")
        for domain in domains
    )
    return youtube_cookie and (has_header or bool(rows))


def install_cookie_data(data: bytes) -> str:
    """Validate and atomically replace the configured cookie file."""
    if not validate_cookie_data(data):
        raise ValueError(
            "Invalid file. Use a Netscape-format cookie file containing YouTube cookies."
        )

    destination = Path(YOUTUBE_FILE).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=".youtube-cookies-", suffix=".tmp", dir=str(destination.parent)
    )
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, destination)
    finally:
        try:
            if os.path.exists(temp_name):
                os.remove(temp_name)
        except OSError:
            pass
    return str(destination)


async def refresh_from_private_url() -> bool:
    if not YOUTUBE_COOKIES_URL:
        return False
    if not YOUTUBE_COOKIES_URL.lower().startswith("https://"):
        logger.warning("YouTube cookie refresh URL must use HTTPS; refresh skipped.")
        return False

    timeout = aiohttp.ClientTimeout(total=30, connect=10)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                YOUTUBE_COOKIES_URL,
                headers={"Accept": "text/plain, application/octet-stream"},
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    logger.warning(
                        "YouTube cookie URL refresh returned HTTP %s.", response.status
                    )
                    return False
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > MAX_COOKIE_BYTES:
                    logger.warning("YouTube cookie URL response is too large; skipped.")
                    return False
                data = await response.content.read(MAX_COOKIE_BYTES + 1)

        install_cookie_data(data)
        logger.info("YouTube cookie file refreshed from configured private URL.")
        return True
    except Exception as error:
        logger.warning("YouTube cookie URL refresh failed: %s", type(error).__name__)
        return False


async def auto_refresh_task():
    if not YOUTUBE_COOKIES_URL:
        logger.info("YouTube URL cookie refresh disabled; admin upload is available.")
        return

    import asyncio

    while True:
        try:
            await refresh_from_private_url()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning("YouTube cookie refresh task error: %s", type(error).__name__)
        await asyncio.sleep(YOUTUBE_COOKIE_REFRESH_HOURS * 3600)
