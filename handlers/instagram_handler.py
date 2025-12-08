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

# Logger setup
logger = setup_logging(logging.DEBUG)
logger.add("instagram_handler.log", rotation="10 MB", level="DEBUG")

# Supported Domains
SUPPORTED_DOMAINS = ["instagram.com"]

# URL Validation
def is_valid_url(url: str) -> bool:
    """Check if the given URL is a valid Instagram link."""
    try:
        result = urlparse(url)
        return (
            result.scheme in ["http", "https"]
            and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
        )
    except ValueError:
        return False

# Identify Instagram Video
def is_instagram_video(url: str) -> bool:
    """Identify if the given URL points to an Instagram video."""
    return any(x in url for x in ["/reel/", "/tv/", "/video/"])

# Progress Hook for Downloads
def download_progress_hook(d: dict) -> None:
    """Track and log download progress."""
    if d.get("status") == "downloading":
        percent = d.get("_percent_str", "0%")
        speed = d.get("_speed_str", "N/A")
        eta = d.get("_eta_str", "N/A")
        logger.info(f"Downloading... {percent} at {speed}, ETA: {eta}")

    elif d.get("status") == "finished":
        logger.info(f"✅ Download finished: {d.get('filename')}")

# Instagram Video Downloader
async def process_instagram(url: str) -> tuple[str | None, int, str | None]:
    """Download Instagram video asynchronously and return its path, size, and any errors."""

    # Ensure clean URL
    url = url.split("#")[0]

    # Validate cookies
    cookie_path = Path(COOKIES_FILE)
    if not cookie_path.exists() or cookie_path.stat().st_size == 0:
        logger.error("❌ Instagram cookies file is missing or empty!")
        return None, 0, "Instagram cookies file is missing or empty"

    output_template = str(Path(DOWNLOAD_DIR) / "%(uploader)s - %(title)s.%(ext)s")

    ydl_opts = {
        "format": "mp4/bv+ba/b",
        "outtmpl": output_template,
        "cookiefile": str(cookie_path),

        # FIX FOR "login required" + "content unavailable"
        "extractor_args": {
            "instagram": {
                "cookiefile": [str(cookie_path)],
                "app_id": ["936619743392459"],
                "viewport_width": ["1080"],
                "post_page_limit": ["2"],
                "include_author": ["1"],
            }
        },

        "http_headers": {
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36",

            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.instagram.com/",
        },

        "socket_timeout": 30,
        "retries": 8,
        "progress_hooks": [download_progress_hook],

        "postprocessors": [
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            # Move extraction to thread to avoid blocking async
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)

            if not info:
                return None, 0, "❌ Failed to extract Instagram info"

            # Prepare final file name
            final_path = Path(ydl.prepare_filename(info))

            size = final_path.stat().st_size if final_path.exists() else 0

            return str(final_path), size, None

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ Instagram download error: {e}")
        return None, 0, str(e)

    except Exception as e:
        logger.error(f"⚠️ Unexpected Instagram error: {e}")
        return None, 0, str(e)

# Send Video to User
async def send_video_to_user(bot, chat_id: int, video_path: str) -> None:
    """Send the downloaded Instagram video to the specified user."""
    try:
        with open(video_path, "rb") as video:
            await bot.send_video(chat_id, video)

        logger.info(f"✅ Video successfully sent to user {chat_id}")

    except Exception as e:
        logger.error(f"❌ Failed to send video to user {chat_id}: {e}")

# Cleanup
def cleanup_video(video_path: str) -> None:
    """Remove the downloaded video file to free up space."""
    video_file = Path(video_path)
    try:
        if video_file.exists():
            video_file.unlink()
            gc.collect()
            logger.info(f"🧹 Cleaned up {video_path}")
    except Exception as e:
        logger.error(f"❌ Failed to clean up {video_path}: {e}")