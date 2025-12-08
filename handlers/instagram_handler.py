# handlers/instagram_handler.py
import os
import gc
import logging
import asyncio
from pathlib import Path
from urllib.parse import urlparse
import yt_dlp
import aiofiles
from typing import Optional, Tuple

from config import DOWNLOAD_DIR
from utils.instagram_cookies import COOKIES_FILE
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging

# Logger setup
logger = setup_logging(logging.DEBUG)
logger.add("instagram_handler.log", rotation="10 MB", level="DEBUG")

SUPPORTED_DOMAINS = ["instagram.com"]

Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)


# ------------------------------
# Validate URL
# ------------------------------
def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ["http", "https"] and any(d in parsed.netloc for d in SUPPORTED_DOMAINS)
    except:
        return False


# ------------------------------
# Recognize Reel / TV / Video
# ------------------------------
def is_instagram_video(url: str) -> bool:
    return any(x in url for x in ["/reel/", "/tv/", "/video/"])


# ------------------------------
# Progress hook
# ------------------------------
def download_progress_hook(d: dict):
    if d.get("status") == "downloading":
        logger.info(f"Downloading {d.get('_percent_str')} at {d.get('_speed_str')} ETA {d.get('_eta_str')}")
    elif d.get("status") == "finished":
        logger.info(f"✅ Download finished: {d.get('filename')}")


# ------------------------------
# FIXED: Skip MP4 Conversion Correctly
# ------------------------------
def skip_mp4_convert(info, *, file_path: str) -> str:
    """
    If file is already .mp4 → return same file
    Otherwise → yt-dlp will convert automatically
    """
    if file_path.lower().endswith(".mp4"):
        logger.info("🟢 File already MP4 → skipping ffmpeg convert.")
        return file_path

    return file_path  # let yt-dlp handle conversion if needed


# ------------------------------
# Instagram Downloader
# ------------------------------
async def process_instagram(url: str) -> Tuple[Optional[str], int, Optional[str]]:
    url = url.split("#")[0]

    cookie_path = Path(COOKIES_FILE)
    if not cookie_path.exists() or cookie_path.stat().st_size == 0:
        return None, 0, "❌ Instagram cookies file is missing or empty"

    OUT_TEMPLATE = str(Path(DOWNLOAD_DIR) / "%(uploader)s-%(id)s.%(ext)s")

    ydl_opts = {
        "format": "bv+ba/b",
        "outtmpl": OUT_TEMPLATE,
        "socket_timeout": 15,
        "retries": 5,
        "cookiefile": str(cookie_path),
        "progress_hooks": [download_progress_hook],

        # ❌ Removed FFmpegVideoConvertor — causes double-convert
        # yt-dlp already outputs mp4 because merge_output_format is set

        "merge_output_format": "mp4",

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0 "
                "Gecko/20100101 Firefox/123.0"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.instagram.com/",
        },
    }

    try:
        def _run():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)

        info = await asyncio.to_thread(_run)

        if not info:
            return None, 0, "❌ Failed to extract Instagram info"

        uploader = info.get("uploader") or "instagram"
        video_id = info.get("id")
        ext = info.get("ext") or "mp4"

        raw_name = f"{uploader}-{video_id}.{ext}"
        safe_name = sanitize_filename(raw_name)

        video_path = Path(DOWNLOAD_DIR) / safe_name

        # Detect actual downloaded file if template mismatch
        if not video_path.exists():
            found = sorted(
                Path(DOWNLOAD_DIR).glob(f"*{video_id}*"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            if found:
                video_path = found[0]

        # 🟢 FIX: If MP4 → skip convert
        final_path = skip_mp4_convert(info, file_path=str(video_path))

        size = video_path.stat().st_size if video_path.exists() else 0

        return str(final_path), size, None

    except Exception as e:
        logger.exception(f"❌ Instagram download failed: {e}")
        return None, 0, str(e)


# ------------------------------
# Send video
# ------------------------------
async def send_video_to_user(bot, chat_id: int, file_path: str):
    try:
        async with aiofiles.open(file_path, "rb") as f:
            data = await f.read()

        await bot.send_video(chat_id, data, supports_streaming=True)
        logger.info(f"📤 Video sent to user {chat_id}")
    except Exception as e:
        logger.error(f"❌ Failed to send video: {e}")


# ------------------------------
# Cleanup
# ------------------------------
def cleanup_video(file_path: str):
    try:
        p = Path(file_path)
        if p.exists():
            p.unlink()
            gc.collect()
            logger.info(f"🧹 Cleaned: {file_path}")
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")