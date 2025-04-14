# processing.py
import os
import gc
import logging
import asyncio
import aiofiles
import re
import dropbox
from dropbox.exceptions import AuthError, ApiError

# Import local modules (assuming they are in the correct path relative to this file)
from config import TELEGRAM_FILE_LIMIT, DROPBOX_ACCESS_TOKEN
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import process_video_trim, process_audio_trim
from handlers.image_handlers import process_instagram_image
from utils.logger import setup_logging

# Logging setup
logger = setup_logging(logging.DEBUG)

# Dropbox client setup
try:
    dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
    # Validate token early
    dbx.users_get_current_account()
    logger.info("Dropbox client initialized and authenticated successfully.")
except AuthError as auth_error:
    logger.error(f"Dropbox authentication failed during initialization: {auth_error}")
    dbx = None # Indicate Dropbox is not available
except ApiError as api_error:
    logger.error(f"Dropbox API error during initialization: {api_error}")
    dbx = None
except Exception as e:
    logger.error(f"Unexpected error initializing Dropbox: {e}")
    dbx = None


# Regex patterns for different platforms
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
    "Instagram": process_instagram, # Note: Specific image handling is separate
    "Facebook": process_facebook,
    "Twitter/X": download_twitter_media,
    "Adult": process_adult,
}

def detect_platform(url):
    """Detects the platform based on URL patterns."""
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None

async def upload_to_dropbox(file_path, filename):
    """
    Uploads a file to Dropbox and returns a shareable link.

    Args:
        file_path (str): Path to the file to upload
        filename (str): Name to use for the file in Dropbox

    Returns:
        str or None: Shareable link to the uploaded file or None on failure
    """
    if not dbx:
        logger.error("Dropbox client not initialized or authentication failed. Cannot upload.")
        return None
    if not os.path.exists(file_path):
        logger.error(f"File not found for Dropbox upload: {file_path}")
        return None

    try:
        dropbox_path = f"/telegram_uploads/{filename}"
        file_size = os.path.getsize(file_path)

        with open(file_path, "rb") as f:
            if file_size > 140 * 1024 * 1024:  # 140 MB threshold for session upload
                logger.info(f"Starting Dropbox upload session for large file: {filename} ({file_size} bytes)")
                chunk_size = 4 * 1024 * 1024
                upload_session_start_result = dbx.files_upload_session_start(f.read(chunk_size))
                cursor = dropbox.files.UploadSessionCursor(
                    session_id=upload_session_start_result.session_id,
                    offset=f.tell()
                )
                commit = dropbox.files.CommitInfo(path=dropbox_path, mode=dropbox.files.WriteMode.overwrite)

                while f.tell() < file_size:
                    if (file_size - f.tell()) <= chunk_size:
                        logger.info(f"Finishing Dropbox upload session for: {filename}")
                        dbx.files_upload_session_finish(f.read(chunk_size), cursor, commit)
                        break
                    else:
                        dbx.files_upload_session_append_v2(f.read(chunk_size), cursor)
                        cursor.offset = f.tell()
                logger.info(f"Finished Dropbox upload session for: {filename}")
            else:
                logger.info(f"Starting direct Dropbox upload for: {filename} ({file_size} bytes)")
                dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)
                logger.info(f"Finished direct Dropbox upload for: {filename}")

        # Create a shareable link
        shared_link_metadata = dbx.sharing_create_shared_link_with_settings(
            dropbox_path,
            settings=dropbox.sharing.SharedLinkSettings(requested_visibility=dropbox.sharing.RequestedVisibility.public)
        )
        # Return direct download link (dl=1)
        return shared_link_metadata.url.replace('?dl=0', '?dl=1')

    except AuthError as auth_error:
        logger.error(f"Dropbox authentication error during upload: {auth_error}")
        return None
    except ApiError as api_error:
        logger.error(f"Dropbox API error during upload: {api_error}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during Dropbox upload for {filename}: {e}", exc_info=True)
        return None

async def process_media_download(url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    """
    Handles video/audio download logic based on platform and type.

    Args:
        url (str): The URL of the media.
        is_audio (bool): Whether to extract audio only.
        is_video_trim (bool): Whether to trim the video.
        is_audio_trim (bool): Whether to trim the audio.
        start_time (str, optional): Start time for trimming (HH:MM:SS).
        end_time (str, optional): End time for trimming (HH:MM:SS).

    Returns:
        tuple: (list_of_file_paths, file_size, download_url) or raises an error.
               file_size and download_url might be None depending on the handler.
               Returns an empty list for file_paths if download fails.
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

        # Handle full audio extraction
        if is_audio:
            logger.info(f"Processing full audio extraction: URL={url}")
            result = await extract_audio_ffmpeg(url)
            if isinstance(result, tuple) and len(result) == 2:
                file_path, file_size = result
                return ([file_path] if file_path else [], file_size, None)
            elif result: # Assuming result is just the file_path
                file_path = result
                file_size = os.path.getsize(file_path) if os.path.exists(file_path) else None
                return ([file_path], file_size, None)
            else:
                raise ValueError("Audio extraction failed or returned unexpected result.")

        # Handle regular video/media downloads
        platform = detect_platform(url)
        if not platform:
            raise ValueError("Unsupported URL platform.")

        logger.info(f"Processing {platform} download: URL={url}")
        handler = PLATFORM_HANDLERS.get(platform)
        if not handler:
             # Handle Instagram images separately if no specific video handler matches
            if platform == "Instagram":
                logger.info("No specific Instagram video handler found, assuming image request for process_instagram_image.")
                # This case is handled by `process_instagram_image_download` now.
                # Returning error here as this function focuses on general media.
                raise ValueError("Use /image command or specific handler for Instagram images.")
            else:
                raise ValueError(f"No handler configured for platform: {platform}")

        result = await handler(url)

        # Standardize return format: (list_of_file_paths, file_size, download_url)
        if isinstance(result, tuple):
            if len(result) >= 3: # paths, size, url
                 paths = result[0] if isinstance(result[0], list) else [result[0]] if result[0] else []
                 return (paths, result[1], result[2])
            elif len(result) == 2: # paths, size
                 paths = result[0] if isinstance(result[0], list) else [result[0]] if result[0] else []
                 return (paths, result[1], None)
            elif len(result) == 1: # Only path(s)
                 paths = result[0] if isinstance(result[0], list) else [result[0]] if result[0] else []
                 size = os.path.getsize(paths[0]) if paths and os.path.exists(paths[0]) else None
                 return (paths, size, None)
            else: # Empty tuple?
                 return ([], None, None)
        elif isinstance(result, list): # List of paths
            paths = result
            size = os.path.getsize(paths[0]) if paths and os.path.exists(paths[0]) else None
            return (paths, size, None)
        elif isinstance(result, str): # Single path
             path = result
             size = os.path.getsize(path) if os.path.exists(path) else None
             return ([path] if path else [], size, None)
        else: # No result or unexpected
            return ([], None, None)

    except Exception as e:
        logger.error(f"Error in process_media_download for URL {url}: {e}", exc_info=True)
        # Re-raise the exception so the caller (worker) can handle messaging the user
        raise

async def process_instagram_image_download(url):
    """
    Handles Instagram image download logic.

    Args:
        url (str): The URL of the Instagram post/story.

    Returns:
        list: A list of file paths for the downloaded images. Returns empty list on failure.
    """
    try:
        logger.info(f"Processing Instagram image: URL={url}")
        result = await process_instagram_image(url)

        # Standardize return format to a list of paths
        if isinstance(result, list):
            file_paths = result
        elif isinstance(result, tuple) and len(result) > 0:
             # Assuming the first element is the path or list of paths
            file_paths = result[0] if isinstance(result[0], list) else [result[0]]
        elif isinstance(result, str):
            file_paths = [result]
        else:
            file_paths = []

        # Filter out non-existent paths
        valid_paths = [fp for fp in file_paths if fp and os.path.exists(fp)]
        if not valid_paths:
            logger.warning(f"No valid image paths found or downloaded for URL: {url}")
            return []

        logger.info(f"Successfully processed Instagram image(s) for URL: {url}. Paths: {valid_paths}")
        return valid_paths

    except Exception as e:
        logger.error(f"Error processing Instagram image download for URL {url}: {e}", exc_info=True)
        # Re-raise the exception for the caller (worker)
        raise

def cleanup_file(file_path):
    """Safely removes a file if it exists."""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up file: {file_path}")
            gc.collect() # Optional: encourage garbage collection
    except OSError as e:
        logger.error(f"Error removing file {file_path}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error cleaning up file {file_path}: {e}")

