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
from utils.logger import setup_logging
from handlers.image_handlers import process_instagram_image

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

        # Use file upload with error handling
        with open(file_path, "rb") as f:
            file_size = os.path.getsize(file_path)

            # Check if file is too large for single upload
            if file_size > 140 * 1024 * 1024:  # 140 MB threshold
                logger.info("Large file detected, using upload session")
                upload_session = dbx.files_upload_session_start(f.read(4*1024*1024))
                cursor = dropbox.files.UploadSessionCursor(
                    session_id=upload_session.session_id, 
                    offset=f.tell()
                )

                while f.tell() < file_size:
                    if (file_size - f.tell()) <= 4*1024*1024:
                        dbx.files_upload_session_finish(
                            f.read(4*1024*1024), 
                            cursor, 
                            dropbox.files.CommitInfo(path=dropbox_path)
                        )
                        break
                    else:
                        dbx.files_upload_session_append_v2(
                            f.read(4*1024*1024), 
                            cursor
                        )
                        cursor.offset = f.tell()
            else:
                # Regular upload for smaller files
                dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)

        # Create shared link with longer expiration
        shared_link = dbx.sharing_create_shared_link_with_settings(
            dropbox_path,
            dropbox.sharing.SharedLinkSettings(
                requested_visibility=dropbox.sharing.RequestedVisibility.public
            )
        )
        return shared_link.url.replace('dl=0', 'dl=1')

    except dropbox.exceptions.AuthError as auth_error:
        logger.error(f"Dropbox authentication error: {auth_error}")
        return None
    except dropbox.exceptions.ApiError as api_error:
        logger.error(f"Dropbox API error: {api_error}")
        return None
    except Exception as e:
        logger.error(f"Unexpected Dropbox upload error: {e}")
        return None

async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    """Handles video/audio download and sends it to Telegram or Dropbox."""
    try:
        request_type = "Video Download"
        if is_audio:
            request_type = "Audio Download"
        elif is_video_trim:
            request_type = "Video Trimming"
        elif is_audio_trim:
            request_type = "Audio Trimming"

        await send_message(message.chat.id, f"📥 **Processing your {request_type.lower()}...**")
        logger.info(f"Processing URL: {url}, Type: {request_type}")

        # Detect platform
        platform = detect_platform(url)
        if not platform:
            await send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        # Handle request based on type
        if is_video_trim:
            logger.info(f"Processing video trim request: Start={start_time}, End={end_time}")
            file_path, file_size = await process_video_trim(url, start_time, end_time)
            download_url = None
            file_paths = [file_path] if file_path else []
        elif is_audio_trim:
            logger.info(f"Processing audio trim request: Start={start_time}, End={end_time}")
            file_path, file_size = await process_audio_trim(url, start_time, end_time)
            download_url = None
            file_paths = [file_path] if file_path else []
        elif is_audio:
            result = await extract_audio_ffmpeg(url)
            if isinstance(result, tuple):
                file_path, file_size = result if len(result) == 2 else (result[0], None)
                download_url = None
                file_paths = [file_path] if file_path else []
            else:
                file_path, file_size, download_url = result, None, None
                file_paths = [file_path] if file_path else []
        else:
            if platform == "Instagram":
                # Determine if it's an image (photo post) or video/reel
                if "/p/" in url or "/reel/" not in url:
                    result = await process_instagram_image(url)
                else:
                    result = await process_instagram(url)
            else:
                result = await PLATFORM_HANDLERS[platform](url)

            # Handle different return formats from platform handlers
            if isinstance(result, tuple) and len(result) >= 3:
                file_paths, file_size, download_url = result
                # Ensure file_paths is always a list
                if not isinstance(file_paths, list):
                    file_paths = [file_paths] if file_paths else []
            elif isinstance(result, tuple) and len(result) == 2:
                file_paths, file_size = result
                download_url = None
                # Ensure file_paths is always a list
                if not isinstance(file_paths, list):
                    file_paths = [file_paths] if file_paths else []
            else:
                file_paths = result if isinstance(result, list) else [result] if result else []
                file_size = None
                download_url = None

        # Log what we received
        logger.info(f"Platform handler returned: file_paths={file_paths}, file_size={file_size}, download_url={download_url}")

        # Skip processing if no files were returned
        if not file_paths or all(not path for path in file_paths):
            logger.warning("No valid file paths returned from platform handler")
            await send_message(message.chat.id, "❌ **Download failed. No media found.**")
            return

        # Process each file (for handlers that may return multiple files like Instagram carousels)
        for file_path in file_paths:
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"File path does not exist: {file_path}")
                continue

            # Get file size if not provided
            if file_size is None:
                file_size = os.path.getsize(file_path)

            # Handle case where file is too large for Telegram
            if file_size > TELEGRAM_FILE_LIMIT:
                # Generate a unique filename
                filename = f"{message.chat.id}_{os.path.basename(file_path)}"

                logger.info(f"Attempting Dropbox upload for file: {filename}")
                logger.info(f"File size: {file_size}")

                # Upload to Dropbox
                dropbox_link = await upload_to_dropbox(file_path, filename)

                if dropbox_link:
                    logger.info(f"Successfully uploaded to Dropbox: {dropbox_link}")
                    await send_message(
                        message.chat.id,
                        f"⚠️ **File too large for Telegram.**\n📥 [Download from Dropbox]({dropbox_link})"
                    )
                else:
                    logger.warning("Dropbox upload failed")
                    # Fallback to original download URL if Dropbox upload fails
                    if download_url:
                        await send_message(
                            message.chat.id,
                            f"⚠️ **File too large for Telegram.**\n📥 [Download here]({download_url})"
                        )
                    else:
                        await send_message(message.chat.id, "❌ **Download failed.**")
            else:
                # Send file to Telegram
                async with aiofiles.open(file_path, "rb") as file:
                    if is_audio or is_audio_trim:
                        await bot.send_audio(message.chat.id, file, timeout=600)
                    else:
                        await bot.send_video(message.chat.id, file, supports_streaming=True, timeout=600)

            # Cleanup the current file
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Cleaned up file: {file_path}")
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up file {file_path}: {cleanup_error}")

        # Force garbage collection
        gc.collect()

    except Exception as e:
        logger.error(f"Comprehensive error in process_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

async def worker():
    """Worker function for parallel processing of downloads."""
    while True:
        message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time = await download_queue.get()
        await process_download(message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time)
        download_queue.task_done()

@bot.message_handler(commands=["start", "help"])
async def send_welcome(message):
    """Sends welcome message with bot instructions."""
    welcome_text = (
        "🤖 *Media Download Bot* 🤖\n\n"
        "I can help you download media from various platforms:\n"
        "• YouTube\n• Instagram\n• Facebook\n• Twitter/X\n\n"
        "Commands:\n"
        "• Send a direct URL to download video\n"
        "• /audio <URL> - Extract full audio from video\n"
        "• /trim <URL> <Start Time> <End Time> - Trim video segment\n"
        "• /trimAudio <URL> <Start Time> <End Time> - Extract audio segment\n\n"
        "Examples:\n"
        "• `/trim https://youtube.com/watch?v=example 00:01:00 00:02:30`\n"
        "• `/trimAudio https://youtube.com/watch?v=example 00:01:00 00:02:30`"
    )
    await send_message(message.chat.id, welcome_text)

@bot.message_handler(commands=["audio"])
async def handle_audio_request(message):
    """Handles audio extraction requests for all platforms."""
    url = message.text.replace("/audio", "").strip()
    if not url:
        await send_message(message.chat.id, "⚠️ **Please provide a URL.**")
        return
    await download_queue.put((message, url, True, False, False, None, None))
    await send_message(message.chat.id, "🎵 **Added to audio extraction queue!**")

@bot.message_handler(commands=["trim"])
async def handle_video_trim_request(message):
    """Handles video trimming requests."""
    match = re.search(r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", message.text)
    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format. Please send: `/trim <URL> <Start Time (HH:MM:SS)> <End Time (HH:MM:SS)>`"
        )
        return

    url, start_time, end_time = match.groups()
    await download_queue.put((message, url, False, True, False, start_time, end_time))
    await send_message(message.chat.id, "✂️🎬 **Added to video trimming queue!**")

@bot.message_handler(commands=["trimAudio"])
async def handle_audio_trim_request(message):
    """Handles audio segment extraction requests."""
    match = re.search(r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", message.text)
    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format. Please send: `/trimAudio <URL> <Start Time (HH:MM:SS)> <End Time (HH:MM:SS)>`"
        )
        return

    url, start_time, end_time = match.groups()
    await download_queue.put((message, url, False, False, True, start_time, end_time))
    await send_message(message.chat.id, "✂️🎵 **Added to audio segment extraction queue!**")

@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    """Handles general video download requests."""
    url = message.text.strip()
    await download_queue.put((message, url, False, False, False, None, None))
    await send_message(message.chat.id, "🎬 **Added to video download queue!**")

async def main():
    """Runs the bot and initializes worker processes."""
    num_workers = min(3, os.cpu_count() or 1)  # Limit workers based on CPU cores
    for _ in range(num_workers):
        asyncio.create_task(worker())  # Start workers in background

    try:
        await bot.infinity_polling(timeout=30)
    except Exception as e:
        logger.error(f"Bot polling error: {e}")

if __name__ == "__main__":
    asyncio.run(main())