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
from utils.instagram_cookies import COOKIES_FILE  # ensure this is a Netscape cookies.txt
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging

# Logger setup
logger = setup_logging(logging.DEBUG)
logger.add("instagram_handler.log", rotation="10 MB", level="DEBUG")

# Supported Domains
SUPPORTED_DOMAINS = ['instagram.com']

# Ensure download dir exists
Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)

# URL Validation
def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return result.scheme in ['http', 'https'] and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
    except ValueError:
        return False

# Identify Instagram Video
def is_instagram_video(url: str) -> bool:
    return any(x in url for x in ['/reel/', '/tv/', '/video/'])

# Progress Hook for Downloads
def download_progress_hook(d: dict) -> None:
    status = d.get('status')
    if status == 'downloading':
        percent = d.get('_percent_str', '0%')
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        logger.info(f"Downloading... {percent} at {speed}, ETA: {eta}")
    elif status == 'finished':
        logger.info(f"✅ Download finished: {d.get('filename')}")

# Instagram Video Downloader
async def process_instagram(url: str) -> Tuple[Optional[str], int, Optional[str]]:
    # Clean URL (strip fragment only)
    url = url.split('#')[0]

    # Validate cookie file exists and is readable
    cookie_path = Path(COOKIES_FILE)
    if not cookie_path.exists() or cookie_path.stat().st_size == 0:
        logger.error("❌ Instagram cookies file is missing or empty!")
        return None, 0, "Instagram cookies file is missing or empty"

    # Output template - sanitize will be applied later
    outtmpl = str(Path(DOWNLOAD_DIR) / '%(uploader)s - %(title)s.%(ext)s')

    ydl_opts = {
        'format': 'bv+ba/b',
        'merge_output_format': 'mp4',
        'outtmpl': outtmpl,
        'socket_timeout': 10,
        'retries': 5,
        'progress_hooks': [download_progress_hook],
        'cookiefile': str(cookie_path),
        # Keep verbose only during debug
        # 'verbose': True,
        'postprocessors': [
            {
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }
        ],
        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0 '
                'Gecko/20100101 Firefox/123.0'
            ),
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.instagram.com/',
        },
    }

    try:
        # Run blocking yt-dlp in threadpool
        def run_extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)

        info_dict = await asyncio.to_thread(run_extract)

        if not info_dict:
            return None, 0, "❌ Failed to extract info"

        # prepare_filename may need a YDL instance; reconstruct safe filename using fields
        uploader = info_dict.get('uploader') or info_dict.get('uploader_id') or 'instagram'
        title = info_dict.get('title') or info_dict.get('id') or 'video'
        ext = info_dict.get('ext') or 'mp4'
        raw_name = f"{uploader} - {title}.{ext}"
        safe_name = sanitize_filename(raw_name)
        video_path = Path(DOWNLOAD_DIR) / safe_name

        # If yt-dlp created a different filename, try to detect it:
        if not video_path.exists():
            # try to find candidate file in DOWNLOAD_DIR modified recently
            candidates = sorted(Path(DOWNLOAD_DIR).glob(f"*{info_dict.get('id','')}*"), key=lambda p: p.stat().st_mtime, reverse=True)
            if candidates:
                video_path = candidates[0]

        file_size = info_dict.get('filesize') or (video_path.stat().st_size if video_path.exists() else 0)
        return str(video_path), int(file_size), None

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ Instagram download error: {e}")
        return None, 0, str(e)
    except Exception as e:
        logger.exception(f"⚠️ Unexpected error downloading Instagram video: {e}")
        return None, 0, str(e)

# Send Video to User (async, non-blocking)
async def send_video_to_user(bot, chat_id: int, video_path: str) -> None:
    try:
        # Read file asynchronously to bytes (careful with very large files)
        async with aiofiles.open(video_path, 'rb') as f:
            data = await f.read()
        await bot.send_video(chat_id, data, supports_streaming=True)
        logger.info(f"✅ Video successfully sent to user {chat_id}")
    except Exception as e:
        logger.error(f"❌ Failed to send video to user {chat_id}: {e}")

# Cleanup Downloaded Files
def cleanup_video(video_path: str) -> None:
    video_file = Path(video_path)
    try:
        if video_file.exists():
            video_file.unlink()
            gc.collect()
            logger.info(f"🧹 Cleaned up {video_path}")
    except Exception as e:
        logger.error(f"❌ Failed to clean up {video_path}: {e}")