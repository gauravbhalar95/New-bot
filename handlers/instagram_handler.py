import logging
import gc
import asyncio
from pathlib import Path
from urllib.parse import urlparse
import yt_dlp
import instaloader
import re
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

# Extract Post ID from URL
def extract_post_id(url: str) -> str:
    """Extract Instagram post ID from URL."""
    # Extract the shortcode from URL
    match = re.search(r'/p/([^/?]+)', url) or re.search(r'/reel/([^/?]+)', url)
    if match:
        return match.group(1)
    return None

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

# Download using Instaloader
async def download_with_instaloader(url: str) -> tuple[str | None, int, str | None]:
    """Download Instagram post using Instaloader."""
    post_id = extract_post_id(url)
    if not post_id:
        logger.error("❌ Could not extract post ID from URL")
        return None, 0, "Invalid Instagram URL format"
    
    output_dir = Path(DOWNLOAD_DIR)
    output_dir.mkdir(exist_ok=True)
    
    try:
        # Create Instaloader instance
        L = instaloader.Instaloader(
            dirname_pattern=str(output_dir),
            filename_pattern="{shortcode}",
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False
        )
        
        # Load session from cookies if available
        cookie_path = Path(INSTAGRAM_FILE)
        if cookie_path.exists() and cookie_path.stat().st_size > 0:
            try:
                L.load_session_from_file(None, str(cookie_path))
                logger.info("✅ Loaded session from cookies")
            except Exception as e:
                logger.warning(f"⚠️ Could not load session from cookies: {e}")
        
        # Download post
        post = instaloader.Post.from_shortcode(L.context, post_id)
        
        # Determine whether to download as image or video
        is_video = post.is_video
        
        # Download the post
        def download_post():
            if is_video:
                # Download video only
                L.download_post(post, target=post_id)
            else:
                # Download image only
                L.download_pic(
                    filename=str(output_dir / f"{post_id}"),
                    url=post.url,
                    mtime=post.date_utc
                )
            
        await asyncio.to_thread(download_post)
        
        # Determine file path and size
        if is_video:
            file_path = output_dir / f"{post_id}.mp4"
        else:
            file_path = output_dir / f"{post_id}.jpg"
        
        if file_path.exists():
            file_size = file_path.stat().st_size
            return str(file_path), file_size, None
        else:
            return None, 0, "❌ File not found after download"
            
    except instaloader.exceptions.InstaloaderException as e:
        logger.error(f"❌ Instaloader error: {e}")
        return None, 0, str(e)
    except Exception as e:
        logger.error(f"⚠️ Unexpected error with Instaloader: {e}")
        return None, 0, str(e)

# Instagram Media Downloader
async def process_instagram(url: str) -> tuple[str | None, int, str | None]:
    """Download Instagram media asynchronously and return its path, size, and any errors."""
    url = url.split('#')[0]
    
    # First try with Instaloader (primary method)
    logger.info(f"Attempting download with Instaloader: {url}")
    file_path, file_size, error = await download_with_instaloader(url)
    
    # If successful, return the result
    if file_path and not error:
        return file_path, file_size, None
    
    # If Instaloader failed, try with yt-dlp as fallback
    logger.info(f"Instaloader failed ({error}), trying with yt-dlp: {url}")
    
    cookie_path = Path(INSTAGRAM_FILE)
    if not cookie_path.exists() or cookie_path.stat().st_size == 0:
        logger.error("❌ Instagram cookies file is missing or empty!")
        return None, 0, "Instagram cookies file is missing or empty"

    ydl_opts = {
        'format': 'bv+ba\b',  # Use 'best' for more flexibility
        'outtmpl': str(Path(DOWNLOAD_DIR) / '%(title)s.%(ext)s'),
        'socket_timeout': 10,
        'retries': 5,
        'cookiefile': str(INSTAGRAM_FILE),
        'progress_hooks': [download_progress_hook],
        'verbose': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.instagram.com/',
            'Origin': 'https://www.instagram.com'
        }
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
        logger.error(f"❌ Instagram download error (yt-dlp): {e}")
        return None, 0, str(e)
    except Exception as e:
        logger.error(f"⚠️ Unexpected error downloading Instagram media (yt-dlp): {e}")
        return None, 0, str(e)

# Send Media to User
async def send_media_to_user(bot, chat_id: int, file_path: str) -> None:
    """Send the downloaded Instagram media to the specified user."""
    try:
        with open(file_path, 'rb') as media:
            if file_path.endswith(('.mp4', '.mov')):
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