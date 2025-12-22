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

# ---------------- CONSTANTS ----------------
SUPPORTED_DOMAINS = ["instagram.com"]

INSTAGRAM_SUCCESS_DELAY = 25
INSTAGRAM_FAIL_DELAY = 60
INSTAGRAM_BLOCK_DELAY = 1800

TELEGRAM_MAX_SIZE = 2 * 1024 * 1024 * 1024

# ---------------- GLOBAL STATE ----------------
INSTAGRAM_LOCK = asyncio.Lock()
INSTAGRAM_DISABLED_UNTIL = 0


# ---------------- SAFETY ----------------
def is_real_file(path: str) -> bool:
    return (
        isinstance(path, str)
        and path
        and path != "/"
        and Path(path).exists()
        and Path(path).is_file()
    )


# ---------------- URL VALIDATION ----------------
def is_valid_url(url: str) -> bool:
    try:
        r = urlparse(url)
        return r.scheme in ("http", "https") and any(d in r.netloc for d in SUPPORTED_DOMAINS)
    except Exception:
        return False


# ---------------- PROGRESS HOOK ----------------
def download_progress_hook(d):
    if d.get("status") == "finished":
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

        L.download_post(post, target=shortcode)

        for f in Path(DOWNLOAD_DIR).glob(f"*{shortcode}*.mp4"):
            return f

    except Exception as e:
        logger.error(f"❌ Instaloader fallback failed: {e}")

    return None


# ---------------- MAIN DOWNLOADER ----------------
async def process_instagram(url: str) -> tuple[str | None, int, str | None]:
    global INSTAGRAM_DISABLED_UNTIL

    async with INSTAGRAM_LOCK:

        if time.time() < INSTAGRAM_DISABLED_UNTIL:
            return None, 0, "Instagram temporarily blocked"

        cookie_path = Path(COOKIES_FILE)
        if not cookie_path.exists() or cookie_path.stat().st_size == 0:
            return None, 0, "Instagram cookies missing"

        output_template = str(Path(DOWNLOAD_DIR) / "%(title)s.%(ext)s")

        ydl_opts = {
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
            "outtmpl": output_template,
            "cookiefile": str(cookie_path),
            "progress_hooks": [download_progress_hook],
            "retries": 0,
            "quiet": True,
        }

        try:
            before = set(Path(DOWNLOAD_DIR).glob("*.mp4"))

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await asyncio.to_thread(ydl.extract_info, url, download=True)

            after = set(Path(DOWNLOAD_DIR).glob("*.mp4"))
            new_files = list(after - before)

            if not new_files:
                raise RuntimeError("No video file created")

            video = max(new_files, key=lambda f: f.stat().st_mtime)
            safe_name = sanitize_filename(video.name)
            final_path = video.with_name(safe_name)

            if video.name != safe_name:
                video.rename(final_path)

            if not is_real_file(str(final_path)):
                raise RuntimeError("Invalid video file")

            size = final_path.stat().st_size
            await asyncio.sleep(INSTAGRAM_SUCCESS_DELAY)
            return str(final_path), size, None

        except yt_dlp.utils.DownloadError as e:
            err = str(e).lower()
            logger.error(f"❌ yt-dlp error: {err}")

            if any(x in err for x in ("login required", "rate-limit")):
                INSTAGRAM_DISABLED_UNTIL = time.time() + INSTAGRAM_BLOCK_DELAY

            fallback = instaloader_fallback(url)
            if fallback and fallback.exists():
                return str(fallback), fallback.stat().st_size, None

            await asyncio.sleep(INSTAGRAM_FAIL_DELAY)
            return None, 0, "Instagram download failed"

        except Exception as e:
            logger.exception("⚠️ Instagram unexpected error")
            return None, 0, str(e)


# ---------------- SEND TO USER ----------------
async def send_video_to_user(bot, chat_id: int, video_path: str):
    if not is_real_file(video_path):
        raise RuntimeError(f"Invalid file path: {video_path}")

    file = Path(video_path)

    with open(file, "rb") as f:
        await bot.send_video(chat_id, f, supports_streaming=True)

    logger.info(f"✅ Sent video to {chat_id}")


# ---------------- CLEANUP ----------------
def cleanup_video(video_path: str):
    try:
        if is_real_file(video_path):
            Path(video_path).unlink()
            gc.collect()
            logger.info(f"🧹 Cleaned {video_path}")
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")