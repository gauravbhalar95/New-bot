import os
import gc
import logging
import asyncio
import aiofiles
import re
import dropbox
from dropbox.exceptions import AuthError, ApiError
from telebot.async_telebot import AsyncTeleBot

# Import local modules
from config import API_TOKEN, TELEGRAM_FILE_LIMIT, DROPBOX_ACCESS_TOKEN
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

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()

# Dropbox client setup
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

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
    "Instagram": process_instagram,
    "Facebook": process_facebook,
    "Twitter/X": download_twitter_media,
    "Adult": process_adult,
}
async def send_message(chat_id, text):
    """Sends a message asynchronously."""
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"Error sending message: {e}")


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
        str: Shareable link to the uploaded file
    """
    try:
        # Validate access token
        try:
            dbx.users_get_current_account()
        except Exception as auth_error:
            logger.error(f"Dropbox authentication failed: {auth_error}")
            return None

        dropbox_path = f"/telegram_uploads/{filename}"
        file_size = os.path.getsize(file_path)

        with open(file_path, "rb") as f:
            if file_size > 140 * 1024 * 1024:  # 140 MB threshold
                logger.info("Large file detected, using upload session")
                upload_session = dbx.files_upload_session_start(f.read(4 * 1024 * 1024))
                cursor = dropbox.files.UploadSessionCursor(
                    session_id=upload_session.session_id,
                    offset=f.tell()
                )

                while f.tell() < file_size:
                    chunk_size = 4 * 1024 * 1024
                    if (file_size - f.tell()) <= chunk_size:
                        dbx.files_upload_session_finish(
                            f.read(chunk_size),
                            cursor,
                            dropbox.files.CommitInfo(path=dropbox_path)
                        )
                        break
                    else:
                        dbx.files_upload_session_append_v2(
                            f.read(chunk_size),
                            cursor
                        )
                        cursor.offset = f.tell()
            else:
                dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)

        shared_link = dbx.sharing_create_shared_link_with_settings(
            dropbox_path,
            dropbox.sharing.SharedLinkSettings(
                requested_visibility=dropbox.sharing.RequestedVisibility.public
            )
        )
        return shared_link.url.replace('dl=0', 'dl=1')

    except AuthError as auth_error:
        logger.error(f"Dropbox authentication error: {auth_error}")
        return None
    except ApiError as api_error:
        logger.error(f"Dropbox API error: {api_error}")
        return None
    except Exception as e:
        logger.error(f"Unexpected Dropbox upload error: {e}")
        return None