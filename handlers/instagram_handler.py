import logging
import gc
import asyncio
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from config import DOWNLOAD_DIR
from utils.instagram_cookies import COOKIES_FILE
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging

# ---------------- LOGGER ----------------
logger = setup_logging(logging.DEBUG)
logger.add("instagram_handler.log", rotation="10 MB", level="DEBUG")

# ---------------- CONSTANTS ----------------
SUPPORTED_DOMAINS = ["instagram.com"]

INSTAGRAM_SUCCESS_DELAY = 25      # seconds
INSTAGRAM_FAIL_DELAY = 60         # seconds
INSTAGRAM_BLOCK_DELAY = 1800      # 30 minutes


# ---------------- URL VALIDATION ----------------
def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return (
            result.scheme in ("http", "https")
            and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
        )
    except Exception:
        return False


def is_instagram_video(url: str) -> bool:
    return any(x in url for x in ("/reel/", "/tv/", "/video/"))


# ---------------- PROGRESS HOOK ----------------
def download_progress_hook(d: dict) -> None:
    if d.get("status") == "downloading":
        logger.info(
            f"Downloading... {d.get('_percent_str')} "
            f"at {d.get('_speed_str')} ETA {d.get('_eta_str')}"
        )
    elif d.get("status") == "finished":
        logger.info(f"✅ Download finished: {d.get('filename')}")


# ---------------- MAIN DOWNLOADER ----------------
async def process_instagram(url: str) -> tuple[str | None, int, str | None]:

    url = url.split("#")[0]

    cookie_path = Path(COOKIES_FILE)
    if not cookie_path.exists() or cookie_path.stat().st_size == 0:
        logger.error("❌ Instagram cookies missing or empty")
        return None, 0, "Instagram cookies missing"

    output_template = str(
        Path(DOWNLOAD_DIR) / "%(uploader)s - %(title)s.%(ext)s"
    )

    ydl_opts = {
        "format": "bv*+ba/b",
        "outtmpl": output_template,
        "cookiefile": str(cookie_path),

        # ✅ SAFE extractor usage
        "extractor_args": {
            "instagram": {
                "api": ["graphql"],
            }
        },

        # ✅ MOBILE fingerprint (critical)
        "http_headers": {
            "User-Agent":
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Mobile Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.instagram.com/",
        },

        "socket_timeout": 30,

        # ❌ retries cause bans
        "retries": 0,

        "progress_hooks": [download_progress_hook],

        "postprocessors": [
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(
                ydl.extract_info, url, download=True
            )

            if not info:
                return None, 0, "Failed to extract Instagram info"

            final_path = Path(ydl.prepare_filename(info))
            final_path = final_path.with_name(
                sanitize_filename(final_path.name)
            )

            size = final_path.stat().st_size if final_path.exists() else 0

            # ✅ success cooldown
            await asyncio.sleep(INSTAGRAM_SUCCESS_DELAY)

            return str(final_path), size, None

    except yt_dlp.utils.DownloadError as e:
        err = str(e)
        logger.error(f"❌ Instagram error: {err}")

        # 🚫 BLOCK DETECTION
        if any(x in err.lower() for x in ("login required", "rate-limit", "not available")):
            logger.error("🚫 Instagram BLOCK detected — cooling down")
            await asyncio.sleep(INSTAGRAM_BLOCK_DELAY)
            return None, 0, "Instagram temporarily blocked"

        await asyncio.sleep(INSTAGRAM_FAIL_DELAY)
        return None, 0, err

    except Exception as e:
        logger.exception("⚠️ Unexpected Instagram error")
        await asyncio.sleep(INSTAGRAM_FAIL_DELAY)
        return None, 0, str(e)


# ---------------- SEND TO USER ----------------
async def send_video_to_user(bot, chat_id: int, video_path: str) -> None:
    try:
        with open(video_path, "rb") as video:
            await bot.send_video(chat_id, video)

        logger.info(f"✅ Video sent to user {chat_id}")

    except Exception as e:
        logger.error(f"❌ Send failed: {e}")


# ---------------- CLEANUP ----------------
def cleanup_video(video_path: str) -> None:
    try:
        file = Path(video_path)
        if file.exists():
            file.unlink()
            gc.collect()
            logger.info(f"🧹 Cleaned up {video_path}")
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")