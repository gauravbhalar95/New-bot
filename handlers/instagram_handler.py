import logging
import gc
from pathlib import Path
from urllib.parse import urlparse
import yt_dlp
from config import DOWNLOAD_DIR, COOKIES_FILE
import utils.instagram_cookies as instagram_cookies
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging

# Logger setup
logger = setup_logging(logging.DEBUG)
if hasattr(logger, "add"):
    logger.add("instagram_handler.log", rotation="10 MB", level="DEBUG")

# Supported Domains
SUPPORTED_DOMAINS = ['instagram.com', 'ddinstagram.com']


def is_valid_url(url: str) -> bool:
    """Check if the given URL is a valid Instagram link."""
    try:
        result = urlparse(url)
        return result.scheme in ['http', 'https'] and any(
            domain in result.netloc for domain in SUPPORTED_DOMAINS
        )
    except ValueError:
        return False


def is_instagram_video(url: str) -> bool:
    """Identify if the given URL points to an Instagram video, reel, or post."""
    return any(x in url for x in ['/reel/', '/reels/', '/tv/', '/video/', '/p/'])


def download_progress_hook(d: dict) -> None:
    """Track and log download progress."""
    if d.get('status') == 'downloading':
        percent = d.get('_percent_str', '0%')
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        logger.info(f"Downloading... {percent} at {speed}, ETA: {eta}")
    elif d.get('status') == 'finished':
        logger.info(f"✅ Download finished: {d.get('filename')}")


def process_instagram(url: str) -> str | None:
    """Download Instagram video synchronously and return its file path."""
    url = url.split('#')[0]

    download_dir = Path(DOWNLOAD_DIR)
    download_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        'format': 'bv*+ba/b',
        'merge_output_format': 'mp4',
        'outtmpl': str(download_dir / '%(uploader)s - %(id)s.%(ext)s'),
        'restrictfilenames': True,
        'socket_timeout': 15,
        'retries': 5,
        'progress_hooks': [download_progress_hook],
        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) '
                'Gecko/20100101 Firefox/123.0'
            ),
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.instagram.com/',
        },
        'postprocessors': [
            {
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }
        ],
    }

    cookie_path = Path(COOKIES_FILE)
    if not cookie_path.exists() or cookie_path.stat().st_size == 0:
        refresh_fn = getattr(instagram_cookies, "refresh_instagram_session", None)
        if callable(refresh_fn):
            refresh_fn()

    if cookie_path.exists() and cookie_path.stat().st_size > 0:
        ydl_opts['cookiefile'] = str(cookie_path)
        logger.info("✅ Using Instagram cookies file.")
    else:
        logger.warning(
            "⚠️ Instagram cookies file is missing or empty; attempting public download without cookies."
        )

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            if not info_dict:
                raise RuntimeError("❌ Failed to extract Instagram video info.")

            if 'entries' in info_dict and info_dict['entries']:
                info_dict = info_dict['entries'][0]

            raw_path = Path(ydl.prepare_filename(info_dict))
            mp4_path = raw_path.with_suffix('.mp4')

            if mp4_path.exists():
                return str(mp4_path)
            if raw_path.exists():
                return str(raw_path)

            raise FileNotFoundError(f"Downloaded file not found: {mp4_path}")

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ Instagram download error: {e}")
        raise
    except Exception as e:
        logger.error(f"⚠️ Unexpected error downloading Instagram video: {e}")
        raise


async def send_video_to_user(bot, chat_id: int, video_path: str) -> None:
    """Send the downloaded Instagram video to the specified user."""
    try:
        with open(video_path, 'rb') as video:
            await bot.send_video(chat_id, video)
        logger.info(f"✅ Video successfully sent to user {chat_id}")
    except Exception as e:
        logger.error(f"❌ Failed to send video to user {chat_id}: {e}")


def cleanup_video(video_path: str) -> None:
    """Remove the downloaded video file to free up space."""
    if not video_path:
        return
    video_file = Path(video_path)
    try:
        if video_file.exists():
            video_file.unlink()
            gc.collect()
            logger.info(f"🧹 Cleaned up {video_path}")
    except Exception as e:
        logger.error(f"❌ Failed to clean up {video_path}: {e}")
