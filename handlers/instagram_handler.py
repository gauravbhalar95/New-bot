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
# Only call logger.add if setup_logging returns a Loguru logger
if hasattr(logger, "add"):
    logger.add("instagram_handler.log", rotation="10 MB", level="DEBUG")

SUPPORTED_DOMAINS = ['instagram.com']

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
    """Identify if the given URL points to an Instagram video or post."""
    return any(x in url for x in ['/reel/', '/reels/', '/tv/', '/video/', '/p/'])

def download_progress_hook(d: dict) -> None:
    """Track and log download progress."""
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '0%')
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        logger.info(f"Downloading... {percent} at {speed}, ETA: {eta}")
    elif d['status'] == 'finished':
        logger.info(f"✅ Download finished: {d.get('filename')}")

async def process_instagram(url: str) -> tuple[str | None, int, str | None]:
    """Download Instagram video asynchronously and return its path, size, and any errors."""
    url = url.split('#')[0]

    cookie_path = Path(COOKIES_FILE)
    if not cookie_path.exists() or cookie_path.stat().st_size == 0:
        logger.error("❌ Instagram cookies file is missing or empty!")
        return None, 0, "Instagram cookies file is missing or empty"

    ydl_opts = {
        'format': 'bv+ba/b',
        'merge_output_format': 'mp4',
        'outtmpl': str(Path(DOWNLOAD_DIR) / '%(uploader)s - %(id)s.%(ext)s'),
        'restrictfilenames': True,
        'socket_timeout': 15,
        'retries': 5,
        'progress_hooks': [download_progress_hook],
        'cookiefile': str(cookie_path),
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

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await asyncio.to_thread(ydl.extract_info, url, True)
            if info_dict:
                video_path = Path(ydl.prepare_filename(info_dict)).with_suffix('.mp4')
                file_size = (
                    info_dict.get('filesize')
                    or info_dict.get('filesize_approx')
                    or (video_path.stat().st_size if video_path.exists() else 0)
                )
                return str(video_path), file_size, None
            return None, 0, "❌ Failed to extract info"
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ Instagram download error: {e}")
        return None, 0, str(e)
    except Exception as e:
        logger.error(f"⚠️ Unexpected error downloading Instagram video: {e}")
        return None, 0, str(e)
