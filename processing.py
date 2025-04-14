#!/usr/bin/env python3

import os
import gc
import logging
import asyncio
import aiofiles
import re
from mega import Mega
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

# Import local modules
from config import (
    TELEGRAM_FILE_LIMIT,
    MEGA_EMAIL,
    MEGA_PASSWORD,
    DOWNLOAD_DIR,
    TEMP_DIR
)
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import process_video_trim, process_audio_trim
from handlers.image_handlers import process_instagram_image
from utils.logger import setup_logging

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 5
CHUNK_SIZE = 4 * 1024 * 1024  # 4MB chunks
MAX_WORKERS = min(4, (os.cpu_count() or 1))

# Logging setup
logger = setup_logging(logging.DEBUG)

# MEGA.nz setup
mega = Mega()
mega_instance = None
thread_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# Platform patterns
PLATFORM_PATTERNS = {
    "YouTube": re.compile(r"(youtube\.com|youtu\.be)"),
    "Instagram": re.compile(r"instagram\.com"),
    "Facebook": re.compile(r"facebook\.com"),
    "Twitter/X": re.compile(r"(x\.com|twitter\.com)"),
    "Adult": re.compile(r"(pornhub\.com|xvideos\.com|redtube\.com|xhamster\.com|xnxx\.com)"),
}

# Platform handlers
PLATFORM_HANDLERS = {
    "YouTube": process_youtube,
    "Instagram": process_instagram,
    "Facebook": process_facebook,
    "Twitter/X": download_twitter_media,
    "Adult": process_adult,
}

def init_mega():
    """Initialize MEGA instance with retry mechanism."""
    global mega_instance
    for attempt in range(MAX_RETRIES):
        try:
            if not MEGA_EMAIL or not MEGA_PASSWORD:
                logger.error("MEGA credentials not set")
                return False

            mega_instance = mega.login(MEGA_EMAIL, MEGA_PASSWORD)
            logger.info("MEGA.nz login successful")
            return True
        except Exception as e:
            logger.error(f"MEGA.nz login attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    return False

# Initialize MEGA on module load
if not init_mega():
    logger.warning("MEGA.nz initialization failed. Upload functionality may be limited.")

@lru_cache(maxsize=1000)
def detect_platform(url):
    """Detects the platform based on URL patterns with caching."""
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None

async def upload_to_mega(file_path, filename):
    """
    Uploads a file to MEGA.nz and returns a shareable link.
    
    Args:
        file_path (str): Path to the file to upload
        filename (str): Name to use for the file in MEGA
    
    Returns:
        str or None: Shareable link to the uploaded file or None on failure
    """
    if not mega_instance:
        if not init_mega():
            logger.error("MEGA client not initialized. Cannot upload.")
            return None

    if not os.path.exists(file_path):
        logger.error(f"File not found for MEGA upload: {file_path}")
        return None

    try:
        # Find or create upload folder
        folder = mega_instance.find('telegram_uploads')
        if not folder:
            folder = mega_instance.create_folder('telegram_uploads')

        file_size = os.path.getsize(file_path)
        logger.info(f"Starting MEGA upload for: {filename} ({file_size} bytes)")

        # Use thread pool for upload
        loop = asyncio.get_event_loop()
        file = await loop.run_in_executor(
            thread_pool,
            lambda: mega_instance.upload(file_path, folder[0])
        )

        if not file:
            logger.error("MEGA upload failed - no file returned")
            return None

        # Get shareable link
        link = await loop.run_in_executor(
            thread_pool,
            lambda: mega_instance.get_link(file)
        )
        
        logger.info(f"MEGA upload successful. Link: {link}")
        return link

    except Exception as e:
        logger.error(f"Error uploading to MEGA: {e}", exc_info=True)
        # Try to reinitialize MEGA connection on failure
        if "not logged in" in str(e).lower():
            logger.info("Attempting to reinitialize MEGA connection...")
            if init_mega():
                return await upload_to_mega(file_path, filename)
        return None

async def process_media_download(url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    """
    Handles video/audio download logic based on platform and type.
    
    Args:
        url (str): The URL of the media
        is_audio (bool): Whether to extract audio only
        is_video_trim (bool): Whether to trim the video
        is_audio_trim (bool): Whether to trim the audio
        start_time (str, optional): Start time for trimming (HH:MM:SS)
        end_time (str, optional): End time for trimming (HH:MM:SS)
    
    Returns:
        tuple: (list_of_file_paths, file_size, download_url)
    """
    try:
        # Handle trimming requests
        if is_video_trim:
            logger.info(f"Processing video trim: URL={url}, Start={start_time}, End={end_time}")
            file_path, file_size = await process_video_trim(url, start_time, end_time)
            return ([file_path] if file_path else [], file_size, None)

        if is_audio_trim:
            logger.info(f"Processing audio trim: URL={url}, Start={start_time}, End={end_time}")
            file_path, file_size = await process_audio_trim(url, start_time, end_time)
            return ([file_path] if file_path else [], file_size, None)

        # Handle audio extraction
        if is_audio:
            logger.info(f"Processing audio extraction: URL={url}")
            result = await extract_audio_ffmpeg(url)
            if isinstance(result, tuple):
                file_path, file_size = result
                return ([file_path] if file_path else [], file_size, None)
            else:
                file_path = result
                file_size = os.path.getsize(file_path) if os.path.exists(file_path) else None
                return ([file_path], file_size, None)

        # Handle regular media downloads
        platform = detect_platform(url)
        if not platform:
            raise ValueError("Unsupported URL platform.")

        logger.info(f"Processing {platform} download: URL={url}")
        handler = PLATFORM_HANDLERS.get(platform)
        if not handler:
            if platform == "Instagram":
                raise ValueError("Use /image command for Instagram images.")
            raise ValueError(f"No handler for platform: {platform}")

        result = await handler(url)

        # Standardize return format
        if isinstance(result, tuple):
            if len(result) >= 3:
                paths = result[0] if isinstance(result[0], list) else [result[0]] if result[0] else []
                return (paths, result[1], result[2])
            elif len(result) == 2:
                paths = result[0] if isinstance(result[0], list) else [result[0]] if result[0] else []
                return (paths, result[1], None)
            else:
                paths = result[0] if isinstance(result[0], list) else [result[0]] if result[0] else []
                size = os.path.getsize(paths[0]) if paths and os.path.exists(paths[0]) else None
                return (paths, size, None)
        elif isinstance(result, list):
            paths = result
            size = os.path.getsize(paths[0]) if paths and os.path.exists(paths[0]) else None
            return (paths, size, None)
        elif isinstance(result, str):
            path = result
            size = os.path.getsize(path) if os.path.exists(path) else None
            return ([path] if path else [], size, None)
        else:
            return ([], None, None)

    except Exception as e:
        logger.error(f"Error in process_media_download: {e}", exc_info=True)
        raise

async def process_instagram_image_download(url):
    """
    Handles Instagram image download logic.
    
    Args:
        url (str): The URL of the Instagram post/story
    
    Returns:
        list: List of file paths for downloaded images
    """
    try:
        logger.info(f"Processing Instagram image: URL={url}")
        result = await process_instagram_image(url)

        # Standardize return format
        if isinstance(result, list):
            file_paths = result
        elif isinstance(result, tuple):
            file_paths = result[0] if isinstance(result[0], list) else [result[0]]
        elif isinstance(result, str):
            file_paths = [result]
        else:
            file_paths = []

        # Validate paths
        valid_paths = [fp for fp in file_paths if fp and os.path.exists(fp)]
        if not valid_paths:
            logger.warning(f"No valid images found for URL: {url}")
            return []

        logger.info(f"Successfully processed Instagram image(s): {valid_paths}")
        return valid_paths

    except Exception as e:
        logger.error(f"Error processing Instagram image: {e}", exc_info=True)
        raise

async def cleanup_file(file_path):
    """Safely removes a file if it exists."""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up file: {file_path}")
            gc.collect()
    except Exception as e:
        logger.error(f"Error cleaning up file {file_path}: {e}")

def create_directories():
    """Creates necessary directories if they don't exist."""
    try:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(TEMP_DIR, exist_ok=True)
        logger.info("Created necessary directories")
    except Exception as e:
        logger.error(f"Error creating directories: {e}")

# Create directories on module load
create_directories()