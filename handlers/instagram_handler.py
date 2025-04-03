import logging
import gc
import asyncio
from pathlib import Path
from urllib.parse import urlparse
import yt_dlp
from config import DOWNLOAD_DIR, INSTAGRAM_FILE
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging

# Logger setup
logger = setup_logging(logging.DEBUG)
logger.add("instagram_handler.log", rotation="10 MB", level="DEBUG")

# Supported Domains
SUPPORTED_DOMAINS = ['instagram.com']

# Content Types
CONTENT_TYPES = {
    'VIDEO': 'video',
    'IMAGE': 'image',
    'STORY': 'story',
    'CAROUSEL': 'carousel'
}

# URL Validation
def is_valid_url(url: str) -> bool:
    """Check if the given URL is a valid Instagram link."""
    try:
        result = urlparse(url)
        return result.scheme in ['http', 'https'] and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
    except ValueError:
        return False

# Identify Instagram Content Type
def identify_instagram_content(url: str) -> str:
    """Identify the type of Instagram content from the URL."""
    if any(x in url for x in ['/reel/', '/tv/', '/video/']):
        return CONTENT_TYPES['VIDEO']
    elif '/stories/' in url:
        return CONTENT_TYPES['STORY']
    elif '/p/' in url:
        # This could be either an image or carousel, but we'll determine this later with metadata
        return CONTENT_TYPES['IMAGE']  # Default, will be refined during extraction
    else:
        return CONTENT_TYPES['IMAGE']  # Default fallback

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
async def process_instagram(url: str) -> tuple[list[str] | None, int, str | None]:
    """
    Download Instagram media (videos, images, stories, carousels) asynchronously 
    and return paths, total size, and any errors.
    """
    # Clean URL to avoid unwanted parameters (Keep query parameters)
    url = url.split('#')[0]    

    # Validate cookies
    cookie_path = Path(INSTAGRAM_FILE)
    if not cookie_path.exists() or cookie_path.stat().st_size == 0:
        logger.error("❌ Instagram cookies file is missing or empty!")
        return None, 0, "Instagram cookies file is missing or empty"

    # Identify content type for logging
    content_type = identify_instagram_content(url)
    logger.info(f"Processing Instagram {content_type}: {url}")

    ydl_opts = {
        'format': 'bv+ba/b',  # Best quality for all media types
        'merge_output_format': 'mp4',          # For videos
        'outtmpl': str(Path(DOWNLOAD_DIR) / '%(title)s.%(ext)s'),
        'socket_timeout': 15,
        'retries': 5,
        'compat_opts': ['instagram:login_all'],  # Compatibility fix
        'force_generic_extractor': False,        # Let yt-dlp choose appropriate extractor
        'progress_hooks': [download_progress_hook],
        'verbose': True,
        'cookiefile': str(cookie_path),
        'extract_flat': False,                  # Extract all info including entries in playlists/carousels
        'playlist_items': 'all',                # Download all items in a carousel
        'extractor_args': {
            'instagram:ap_user': ['1'],
            'instagram:viewport_width': ['1920'],
        },
        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0 '
                'Gecko/20100101 Firefox/123.0'
            ),
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.instagram.com/',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Dest': 'document'
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
            logger.info(f"Starting extraction for {url}")
            info_dict = await asyncio.to_thread(ydl.extract_info, url, False)
            
            # Handle different content types
            if info_dict:
                logger.info(f"Successfully extracted info for {url}")
                
                # Check if it's a carousel/playlist with multiple entries
                if '_type' in info_dict and info_dict['_type'] == 'playlist':
                    logger.info(f"Detected carousel with {len(info_dict.get('entries', []))} items")
                    
                    # Download all entries in the carousel
                    media_paths = []
                    total_size = 0
                    
                    for entry in info_dict.get('entries', []):
                        entry_info = await asyncio.to_thread(ydl.process_ie_result, entry, download=True)
                        if entry_info:
                            filename = ydl.prepare_filename(entry_info)
                            media_path = Path(filename)
                            if media_path.exists():
                                media_paths.append(str(media_path))
                                file_size = entry_info.get('filesize', media_path.stat().st_size)
                                total_size += file_size
                                logger.info(f"Downloaded carousel item: {filename}, size: {file_size}")
                    
                    return media_paths, total_size, None
                else:
                    # Single media item (image, video, or story)
                    info_dict = await asyncio.to_thread(ydl.extract_info, url, True)
                    video_path = Path(ydl.prepare_filename(info_dict))
                    
                    if video_path.exists():
                        file_size = info_dict.get('filesize', video_path.stat().st_size)
                        logger.info(f"Downloaded single media: {video_path}, size: {file_size}")
                        return [str(video_path)], file_size, None
            
            logger.error("❌ Failed to extract any media")
            return None, 0, "Failed to extract media information"
            
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ Instagram download error: {e}")
        return None, 0, str(e)
    except Exception as e:
        logger.error(f"⚠️ Unexpected error downloading Instagram media: {e}")
        return None, 0, str(e)

# Send Media to User
async def send_media_to_user(bot, chat_id: int, media_paths: list[str]) -> None:
    """Send the downloaded Instagram media to the specified user."""
    if not media_paths:
        await bot.send_message(chat_id, "Sorry, no media was found or downloaded.")
        return
        
    for media_path in media_paths:
        path = Path(media_path)
        if not path.exists():
            logger.error(f"❌ Media file not found: {media_path}")
            continue
            
        try:
            # Determine file type based on extension
            file_ext = path.suffix.lower()
            
            if file_ext in ['.mp4', '.mov', '.avi']:
                # Send as video
                with open(media_path, 'rb') as video:
                    await bot.send_video(chat_id, video)
                logger.info(f"✅ Video successfully sent to user {chat_id}: {media_path}")
            elif file_ext in ['.jpg', '.jpeg', '.png', '.webp']:
                # Send as photo
                with open(media_path, 'rb') as photo:
                    await bot.send_photo(chat_id, photo)
                logger.info(f"✅ Image successfully sent to user {chat_id}: {media_path}")
            else:
                # Send as document (fallback)
                with open(media_path, 'rb') as document:
                    await bot.send_document(chat_id, document)
                logger.info(f"✅ Document successfully sent to user {chat_id}: {media_path}")
                
        except Exception as e:
            logger.error(f"❌ Failed to send media to user {chat_id}: {e}")

# Cleanup Downloaded Files
def cleanup_media(media_paths: list[str]) -> None:
    """Remove the downloaded media files to free up space."""
    for media_path in media_paths:
        file_path = Path(media_path)
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"🧹 Cleaned up {media_path}")
        except Exception as e:
            logger.error(f"❌ Failed to clean up {media_path}: {e}")
    
    # Force garbage collection
    gc.collect()
    logger.info("🧹 Completed media cleanup and garbage collection")