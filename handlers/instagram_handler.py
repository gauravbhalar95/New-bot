import logging
import gc
import asyncio
import time
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
import instaloader

from config import DOWNLOAD_DIR
from utils.instagram_cookies import COOKIES_FILE
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging

# ---------------- LOGGER ----------------
logger = setup_logging(logging.DEBUG)
logger.add("instagram_handler.log", rotation="10 MB", level="DEBUG")

# ---------------- CONSTANTS ----------------
SUPPORTED_DOMAINS = ["instagram.com"]

INSTAGRAM_SUCCESS_DELAY = 25
INSTAGRAM_FAIL_DELAY = 60
INSTAGRAM_BLOCK_DELAY = 1800  # 30 minutes

TELEGRAM_MAX_SIZE = 2 * 1024 * 1024 * 1024

# ---------------- GLOBAL STATE ----------------
INSTAGRAM_LOCK = asyncio.Lock()
INSTAGRAM_DISABLED_UNTIL = 0  # timestamp


# ---------------- URL VALIDATION ----------------
def is_valid_url(url: str) -> bool:
    try:
        r = urlparse(url)
        return r.scheme in ("http", "https") and any(d in r.netloc for d in SUPPORTED_DOMAINS)
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


# ---------------- INSTALOADER FALLBACK ----------------
def instaloader_fallback(url: str) -> Path | None:
    try:
        shortcode = url.rstrip("/").split("/")[-1]

        L = instaloader.Instaloader(
            download_pictures=False,
            download_video_thumbnails=False,
            save_metadata=False,
            quiet=True,
        )

        L.load_session_from_file(None, COOKIES_FILE)

        post = instaloader.Post.from_shortcode(L.context, shortcode)

        if not post.is_video:
            return None

        output = Path(DOWNLOAD_DIR) / f"{post.owner_username}-{shortcode}.mp4"
        L.download_post(post, target=output.stem)

        for f in Path(DOWNLOAD_DIR).glob(f"*{shortcode}*.mp4"):
            return f

    except Exception as e:
        logger.error(f"❌ Instaloader fallback failed: {e}")

    return None


# ---------------- MAIN DOWNLOADER ----------------
async def process_instagram(url: str) -> tuple[str | None, int, str | None]:
    global INSTAGRAM_DISABLED_UNTIL

    async with INSTAGRAM_LOCK:

        # ⛔ Auto-disable window
        if time.time() < INSTAGRAM_DISABLED_UNTIL:
            return None, 0, "Instagram temporarily disabled due to blocking"

        url = url.split("#")[0]

        cookie_path = Path(COOKIES_FILE)
        if not cookie_path.exists() or cookie_path.stat().st_size == 0:
            return None, 0, "Instagram cookies missing"

        output_template = str(
            Path(DOWNLOAD_DIR) / "%(uploader)s - %(title)s.%(ext)s"
        )

        ydl_opts = {
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
            "outtmpl": output_template,
            "cookiefile": str(cookie_path),

            "extractor_args": {
                "instagram": {"api": ["graphql"]}
            },

            "http_headers": {
                "User-Agent":
                    "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Mobile Safari/537.36",
                "Referer": "https://www.instagram.com/",
            },

            "socket_timeout": 30,
            "retries": 0,
            "progress_hooks": [download_progress_hook],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(
                    ydl.extract_info, url, download=True
                )

                if not info:
                    raise yt_dlp.utils.DownloadError("Empty info")

                final_path = Path(ydl.prepare_filename(info))
                final_path = final_path.with_name(
                    sanitize_filename(final_path.name)
                )

                size = final_path.stat().st_size if final_path.exists() else 0

                await asyncio.sleep(INSTAGRAM_SUCCESS_DELAY)
                return str(final_path), size, None

        except yt_dlp.utils.DownloadError as e:
            err = str(e).lower()
            logger.error(f"❌ yt-dlp failed: {err}")

            # 🚫 Block detection
            if any(x in err for x in ("login required", "rate-limit", "not available")):
                logger.error("🚫 Instagram BLOCK detected → auto-disable enabled")
                INSTAGRAM_DISABLED_UNTIL = time.time() + INSTAGRAM_BLOCK_DELAY

            # 🔁 Instaloader fallback
            fallback_file = instaloader_fallback(url)
            if fallback_file and fallback_file.exists():
                size = fallback_file.stat().st_size
                return str(fallback_file), size, None

            await asyncio.sleep(INSTAGRAM_FAIL_DELAY)
            return None, 0, "Instagram download failed"

        except Exception as e:
            logger.exception("⚠️ Unexpected Instagram error")
            await asyncio.sleep(INSTAGRAM_FAIL_DELAY)
            return None, 0, str(e)


# ---------------- SEND TO USER ----------------
async def send_video_to_user(bot, chat_id: int, video_path: str) -> None:
    try:
        file = Path(video_path)
        size = file.stat().st_size

        if size > TELEGRAM_MAX_SIZE:
            raise ValueError("File too large for Telegram")

        with open(file, "rb") as video:
            if file.suffix.lower() == ".mp4":
                await bot.send_video(chat_id, video, supports_streaming=True)
            else:
                await bot.send_document(chat_id, video)

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