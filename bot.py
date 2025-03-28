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
from handlers.trim_handlers import process_youtube_request
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

async def process_download(message, url, is_audio=False, is_trim_request=False, start_time=None, end_time=None):
    """Handles video/audio download and sends it to Telegram or Dropbox."""
    try:
        await send_message(message.chat.id, "📥 **Processing your request...**")
        logger.info(f"Processing URL: {url}")

        # Detect platform
        platform = detect_platform(url)
        if not platform:
            await send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        # Handle request based on type
        if is_audio:
            result = await extract_audio_ffmpeg(url)
        elif is_trim_request and platform == "YouTube":
            result = await process_youtube_request(url, start_time, end_time)
        else:
            result = await PLATFORM_HANDLERS[platform](url)

        # Process result
        if isinstance(result, tuple):
            file_path, file_size, download_url = result if len(result) == 3 else (*result, None)
        else:
            file_path, file_size, download_url = result, None, None

        # If file is too large for Telegram, upload to Dropbox
        if not file_path or (file_size and file_size > TELEGRAM_FILE_LIMIT):
            if file_path and os.path.exists(file_path):
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

            # Cleanup
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

            gc.collect()
            return

        # Send file to Telegram
        async with aiofiles.open(file_path, "rb") as file:
            if is_audio:
                await bot.send_audio(message.chat.id, file, timeout=600)
            else:
                await bot.send_video(message.chat.id, file, supports_streaming=True, timeout=600)

        # Cleanup
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        gc.collect()

    except Exception as e:
        logger.error(f"Comprehensive error in process_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

async def worker():
    """Worker function for parallel processing of downloads."""
    while True:
        message, url, is_audio, is_trim_request, start_time, end_time = await download_queue.get()
        await process_download(message, url, is_audio, is_trim_request, start_time, end_time)
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
        "• /audio <URL> - Extract audio\n"
        "• /trim <YouTube URL> <Start Time> <End Time> - Trim YouTube video\n\n"
        "Example: `/trim https://youtube.com/video 00:01:00 00:02:30`"
    )
    await send_message(message.chat.id, welcome_text)

@bot.message_handler(commands=["audio"])
async def handle_audio_request(message):
    """Handles audio extraction requests for all platforms."""
    url = message.text.replace("/audio", "").strip()
    if not url:
        await send_message(message.chat.id, "⚠️ **Please provide a URL.**")
        return
    await download_queue.put((message, url, True, False, None, None))
    await send_message(message.chat.id, "✅ **Added to audio queue!**")

@bot.message_handler(commands=["trim"])
async def handle_trim_request(message):
    """Handles YouTube video trimming requests."""
    match = re.search(r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", message.text)
    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format. Please send: `/trim <YouTube URL> <Start Time (HH:MM:SS)> <End Time (HH:MM:SS)>`"
        )
        return

    url, start_time, end_time = match.groups()
    await download_queue.put((message, url, False, True, start_time, end_time))
    await send_message(message.chat.id, "✂️ **Added to trimming queue!**")

@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    """Handles general video download requests."""
    url = message.text.strip()
    await download_queue.put((message, url, False, False, None, None))
    await send_message(message.chat.id, "✅ **Added to download queue!**")

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
