import logging
import gc
import asyncio
from pathlib import Path
from urllib.parse import urlparse
import yt_dlp
from config import DOWNLOAD_DIR, INSTAGRAM_FILE
from utils.logger import setup_logging

# Logger setup
logger = setup_logging(logging.DEBUG)
logger.add("instagram_handler.log", rotation="10 MB", level="DEBUG")

# Supported Domains
SUPPORTED_DOMAINS = ['instagram.com']

# URL Validation
def is_valid_url(url: str) -> bool:
    """Check if the given URL is a valid Instagram link."""
    try:
        result = urlparse(url)
        return result.scheme in ['http', 'https'] and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
    except ValueError:
        return False

# Identify Instagram Media
def is_instagram_video(url: str) -> bool:
    """Identify if the given URL points to an Instagram video."""
    return any(x in url for x in ['/reel/', '/tv/', '/video/'])

def is_instagram_image(url: str) -> bool:
    """Identify if the given URL points to an Instagram image."""
    return '/p/' in url

# Progress Hook for Downloads
def download_progress_hook(d: dict) -> None:
    """Track and log download progress."""
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '0%')
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        logger.info(f"Downloading... {percent} at {speed}, ETA: {eta}")
    elif d['status'] == 'finished':
        logger.info(f"✅ Download finished: {d['filename']}")

# Instagram Media Downloader
async def process_instagram(url: str) -> tuple[str | None, int, str | None]:
    """Download Instagram media asynchronously and return its path, size, and any errors."""
    url = url.split('#')[0]
    cookie_path = Path(INSTAGRAM_FILE)
    if not cookie_path.exists() or cookie_path.stat().st_size == 0:
        logger.error("❌ Instagram cookies file is missing or empty!")
        return None, 0, "Instagram cookies file is missing or empty"
    
    ydl_opts = {
        'format': 'bv+ba/b' if is_instagram_video(url) else 'b',
        'merge_output_format': 'mp4' if is_instagram_video(url) else 'jpg',
        'outtmpl': str(Path(DOWNLOAD_DIR) / '%(title)s.%(ext)s'),
        'socket_timeout': 10,
        'retries': 5,
        'cookiefile': str(cookie_path),
        'progress_hooks': [download_progress_hook],
        'verbose': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await asyncio.to_thread(ydl.extract_info, url, True)
            if info_dict:
                file_path = Path(ydl.prepare_filename(info_dict))
                file_size = info_dict.get('filesize', file_path.stat().st_size if file_path.exists() else 0)
                return str(file_path), file_size, None
            return None, 0, "❌ Failed to extract info"
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ Instagram download error: {e}")
        return None, 0, str(e)
    except Exception as e:
        logger.error(f"⚠️ Unexpected error downloading Instagram media: {e}")
        return None, 0, str(e)

# Send Media to User
async def send_media_to_user(bot, chat_id: int, file_path: str) -> None:
    """Send the downloaded Instagram media to the specified user."""
    try:
        with open(file_path, 'rb') as media:
            if file_path.endswith('.mp4'):
                await bot.send_video(chat_id, media)
            else:
                await bot.send_photo(chat_id, media)
        logger.info(f"✅ Media successfully sent to user {chat_id}")
    except Exception as e:
        logger.error(f"❌ Failed to send media to user {chat_id}: {e}")

# Cleanup Downloaded Files
def cleanup_file(file_path: str) -> None:
    """Remove the downloaded file to free up space."""
    file = Path(file_path)
    try:
        if file.exists():
            file.unlink()
            gc.collect()
            logger.info(f"🧹 Cleaned up {file_path}")
    except Exception as e:
        logger.error(f"❌ Failed to clean up {file_path}: {e}")
