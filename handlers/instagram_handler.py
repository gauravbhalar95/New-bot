import logging
import gc
import asyncio
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from config import DOWNLOAD_DIR
from utils.instagram_cookies import COOKIES_FILE
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging


# ================= LOGGER =================
logger = setup_logging(logging.DEBUG)
logger.add("instagram_handler.log", rotation="10 MB", level="DEBUG")


# ================= CONSTANTS =================
SUPPORTED_DOMAINS = ["instagram.com"]


# ================= URL VALIDATION =================
def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return result.scheme in ("http", "https") and any(
            d in result.netloc for d in SUPPORTED_DOMAINS
        )
    except Exception:
        return False


def is_instagram_video(url: str) -> bool:
    return any(x in url for x in ("/reel/", "/tv/", "/video/"))


# ================= PROGRESS HOOK =================
def download_progress_hook(d: dict) -> None:
    if d["status"] == "downloading":
        logger.info(
            f"⬇ {d.get('_percent_str', '')} "
            f"at {d.get('_speed_str', '')} "
            f"ETA {d.get('_eta_str', '')}"
        )
    elif d["status"] == "finished":
        logger.info(f"✅ Download finished: {d.get('filename')}")


# ================= AUDIO CHECK =================
def has_audio(video_path: Path) -> bool:
    """
    Ensure audio stream exists (prevents silent Telegram videos)
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "json",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return '"index"' in result.stdout
    except Exception as e:
        logger.error(f"Audio check failed: {e}")
        return False


# ================= MAIN DOWNLOAD FUNCTION =================
async def process_instagram(url: str) -> tuple[str | None, int, str | None]:
    """
    Download Instagram Reel with BEST video + BEST audio
    """

    url = url.split("#")[0]

    cookie_path = Path(COOKIES_FILE)
    if not cookie_path.exists() or cookie_path.stat().st_size == 0:
        return None, 0, "❌ Instagram cookies file missing or empty"

    output_dir = Path(DOWNLOAD_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        # 🔥 BEST QUALITY VIDEO + AUDIO
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b",

        "merge_output_format": "mp4",

        "outtmpl": str(
            output_dir / "%(uploader)s - %(title)s.%(ext)s"
        ),

        "cookiefile": str(cookie_path),

        "retries": 5,
        "socket_timeout": 20,

        "progress_hooks": [download_progress_hook],

        # ❌ NEVER USE generic extractor for Instagram
        # "force_generic_extractor": True,

        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.instagram.com/",
        },

        # 🎬 Merge audio + video correctly
        "postprocessors": [
            {"key": "FFmpegMerger"}
        ],

        "verbose": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(
                ydl.extract_info, url, True
            )

            if not info:
                return None, 0, "❌ Failed to extract info"

            file_path = Path(ydl.prepare_filename(info))

            if not file_path.exists():
                return None, 0, "❌ Downloaded file not found"

            # 🔒 Ensure audio exists
            if not has_audio(file_path):
                return None, 0, "❌ Downloaded video has no audio"

            file_size = file_path.stat().st_size
            return str(file_path), file_size, None

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Instagram download error: {e}")
        return None, 0, str(e)

    except Exception as e:
        logger.exception("Unexpected Instagram error")
        return None, 0, str(e)


# ================= SEND TO TELEGRAM =================
async def send_video_to_user(bot, chat_id: int, video_path: str) -> None:
    try:
        with open(video_path, "rb") as video:
            await bot.send_video(
                chat_id,
                video,
                supports_streaming=True
            )
        logger.info(f"📤 Sent video to {chat_id}")
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")


# ================= CLEANUP =================
def cleanup_video(video_path: str) -> None:
    try:
        path = Path(video_path)
        if path.exists():
            path.unlink()
            gc.collect()
            logger.info(f"🧹 Cleaned {video_path}")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")