#!/usr/bin/env python3

import os
import gc
import time
import logging
import asyncio
import aiofiles
import re
from mega import Mega
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple, Optional, Union, Dict, Any

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
VALID_FILE_TYPES = ('.mp4', '.mp3', '.avi', '.mkv', '.jpg', '.jpeg', '.png', '.gif')

# Logging setup
logger = setup_logging(logging.DEBUG)

# MEGA.nz setup
mega = Mega()
mega_instance = None
thread_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# Platform patterns with improved regex
PLATFORM_PATTERNS: Dict[str, re.Pattern] = {
    "YouTube": re.compile(r"(?:youtube\.com/\S*(?:(?:/e(?:mbed)?)?/|watch\?(?:\S*?&?v=))|youtu\.be/)[a-zA-Z0-9_-]+"),
    "Instagram": re.compile(r"(?:instagram\.com|instagr\.am)/(?:p|reel|tv)/[a-zA-Z0-9_-]+"),
    "Facebook": re.compile(r"(?:facebook\.com|fb\.watch)/(?:watch/?\?v=|video\.php\?v=|[^/]+/videos/)[0-9]+"),
    "Twitter/X": re.compile(r"(?:twitter\.com|x\.com)/\w+/status/[0-9]+"),
    "Adult": re.compile(r"(?:pornhub\.com|xvideos\.com|redtube\.com|xhamster\.com|xnxx\.com)/\S+"),
}

# Platform handlers with type hints
PLATFORM_HANDLERS: Dict[str, Any] = {
    "YouTube": process_youtube,
    "Instagram": process_instagram,
    "Facebook": process_facebook,
    "Twitter/X": download_twitter_media,
    "Adult": process_adult,
}

class MEGAUploadError(Exception):
    """Custom exception for MEGA upload failures."""
    pass

def init_mega() -> bool:
    """
    Initialize MEGA instance with retry mechanism.
    
    Returns:
        bool: True if initialization successful, False otherwise
    """
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

@lru_cache(maxsize=1000)
def detect_platform(url: str) -> Optional[str]:
    """
    Detects the platform based on URL patterns with caching.
    
    Args:
        url (str): The URL to check
        
    Returns:
        Optional[str]: Platform name if detected, None otherwise
    """
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None

def is_valid_file(file_path: str) -> bool:
    """
    Check if file exists and has a valid extension.
    
    Args:
        file_path (str): Path to the file
        
    Returns:
        bool: True if file is valid, False otherwise
    """
    return (
        file_path 
        and os.path.exists(file_path) 
        and os.path.isfile(file_path)
        and os.path.splitext(file_path)[1].lower() in VALID_FILE_TYPES
    )

async def upload_to_mega(file_path: str, filename: str) -> Optional[str]:
    """
    Uploads a file to MEGA.nz and returns a shareable link.
    
    Args:
        file_path (str): Path to the file to upload
        filename (str): Name to use for the file in MEGA
        
    Returns:
        Optional[str]: Shareable link to the uploaded file or None on failure
        
    Raises:
        MEGAUploadError: If upload fails
    """
    if not mega_instance and not init_mega():
        raise MEGAUploadError("MEGA client not initialized")

    if not is_valid_file(file_path):
        raise MEGAUploadError(f"Invalid file for upload: {file_path}")

    try:
        # Find or create upload folder
        folder = mega_instance.find('telegram_uploads')
        if not folder:
            folder = mega_instance.create_folder('telegram_uploads')

        file_size = os.path.getsize(file_path)
        logger.info(f"Starting MEGA upload for: {filename} ({file_size / 1024 / 1024:.2f} MB)")

        # Use thread pool for upload
        loop = asyncio.get_event_loop()
        file = await loop.run_in_executor(
            thread_pool,
            lambda: mega_instance.upload(file_path, folder[0])
        )

        if not file:
            raise MEGAUploadError("Upload failed - no file returned")

        # Get shareable link
        link = await loop.run_in_executor(
            thread_pool,
            lambda: mega_instance.get_link(file)
        )
        
        logger.info(f"MEGA upload successful: {filename}")
        return link

    except Exception as e:
        logger.error(f"Error uploading to MEGA: {e}", exc_info=True)
        if "not logged in" in str(e).lower():
            logger.info("Attempting to reinitialize MEGA connection...")
            if init_mega():
                return await upload_to_mega(file_path, filename)
        raise MEGAUploadError(f"Upload failed: {str(e)}")

async def process_media_download(
    url: str,
    is_audio: bool = False,
    is_video_trim: bool = False,
    is_audio_trim: bool = False,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
) -> Tuple[List[str], Optional[int], Optional[str]]:
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
        Tuple[List[str], Optional[int], Optional[str]]: 
            (list_of_file_paths, file_size, download_url)
    
    Raises:
        ValueError: If platform or handler is not supported
    """
    try:
        # Handle trimming requests
        if is_video_trim or is_audio_trim:
            trim_type = "video" if is_video_trim else "audio"
            logger.info(f"Processing {trim_type} trim: URL={url}, Start={start_time}, End={end_time}")
            
            handler = process_video_trim if is_video_trim else process_audio_trim
            file_path, file_size = await handler(url, start_time, end_time)
            
            return ([file_path] if file_path else [], file_size, None)

        # Handle audio extraction
        if is_audio:
            logger.info(f"Processing audio extraction: URL={url}")
            result = await extract_audio_ffmpeg(url)
            
            if isinstance(result, tuple):
                file_path, file_size = result
                return ([file_path] if file_path else [], file_size, None)
            
            file_path = result
            file_size = os.path.getsize(file_path) if is_valid_file(file_path) else None
            return ([file_path], file_size, None)

        # Handle regular media downloads
        platform = detect_platform(url)
        if not platform:
            raise ValueError(f"Unsupported URL platform: {url}")

        handler = PLATFORM_HANDLERS.get(platform)
        if not handler:
            if platform == "Instagram":
                raise ValueError("Use /image command for Instagram images")
            raise ValueError(f"No handler for platform: {platform}")

        logger.info(f"Processing {platform} download: URL={url}")
        result = await handler(url)

        return standardize_result(result)

    except Exception as e:
        logger.error(f"Error in process_media_download: {e}", exc_info=True)
        raise

def standardize_result(
    result: Union[Tuple, List, str, None]
) -> Tuple[List[str], Optional[int], Optional[str]]:
    """
    Standardizes the return format from various handlers.
    
    Args:
        result: The result from a handler function
        
    Returns:
        Tuple[List[str], Optional[int], Optional[str]]:
            (list_of_file_paths, file_size, download_url)
    """
    if isinstance(result, tuple):
        if len(result) >= 3:
            paths = result[0] if isinstance(result[0], list) else [result[0]] if result[0] else []
            return (paths, result[1], result[2])
        elif len(result) == 2:
            paths = result[0] if isinstance(result[0], list) else [result[0]] if result[0] else []
            return (paths, result[1], None)
        else:
            paths = result[0] if isinstance(result[0], list) else [result[0]] if result[0] else []
            size = os.path.getsize(paths[0]) if paths and is_valid_file(paths[0]) else None
            return (paths, size, None)
    elif isinstance(result, list):
        paths = result
        size = os.path.getsize(paths[0]) if paths and is_valid_file(paths[0]) else None
        return (paths, size, None)
    elif isinstance(result, str):
        path = result
        size = os.path.getsize(path) if is_valid_file(path) else None
        return ([path] if path else [], size, None)
    else:
        return ([], None, None)

async def process_instagram_image_download(url: str) -> List[str]:
    """
    Handles Instagram image download logic.
    
    Args:
        url (str): The URL of the Instagram post/story
    
    Returns:
        List[str]: List of file paths for downloaded images
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
        valid_paths = [fp for fp in file_paths if is_valid_file(fp)]
        if not valid_paths:
            logger.warning(f"No valid images found for URL: {url}")
            return []

        logger.info(f"Successfully processed Instagram image(s): {len(valid_paths)} files")
        return valid_paths

    except Exception as e:
        logger.error(f"Error processing Instagram image: {e}", exc_info=True)
        raise

async def cleanup_file(file_path: str) -> None:
    """
    Safely removes a file if it exists.
    
    Args:
        file_path (str): Path to the file to remove
    """
    try:
        if is_valid_file(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up file: {file_path}")
            gc.collect()
    except Exception as e:
        logger.error(f"Error cleaning up file {file_path}: {e}")

def create_directories() -> None:
    """Creates necessary directories if they don't exist."""
    try:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(TEMP_DIR, exist_ok=True)
        logger.info("Created necessary directories")
    except Exception as e:
        logger.error(f"Error creating directories: {e}")

# Initialize on module load
create_directories()
if not init_mega():
    logger.warning("MEGA.nz initialization failed. Upload functionality may be limited.")