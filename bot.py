import os
import gc
import logging
import asyncio
import aiofiles
import re
from mega import Mega
from telebot.async_telebot import AsyncTeleBot
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import local modules
from config import (
    API_TOKEN, 
    TELEGRAM_FILE_LIMIT, 
    MEGA_EMAIL, 
    MEGA_PASSWORD,
    DOWNLOAD_DIR,
    MAX_WORKERS
)
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import process_video_trim, process_audio_trim
from handlers.image_handlers import process_instagram_image
from utils.logger import setup_logging

# Ensure download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Logging setup
logger = setup_logging(logging.DEBUG)

# Verify credentials
if not all([API_TOKEN, MEGA_EMAIL, MEGA_PASSWORD]):
    logger.error("Missing required credentials. Please check your .env file")
    raise ValueError("Missing required credentials")

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()

# Regex patterns for different platforms
PLATFORM_PATTERNS = {
    "YouTube": re.compile(r"(youtube\.com|youtu\.be)"),
    "Instagram": re.compile(r"instagram\.com"),
    "Facebook": re.compile(r"facebook\.com"),
    "Twitter/X": re.compile(r"(x\.com|twitter\.com)"),
    "Adult": re.compile(r"(pornhub\.com|xvideos\.com|redtube\.com|xhamster\.com|xnxx\.com)"),
}

# Platform handlers mapping
PLATFORM_HANDLERS = {
    "YouTube": process_youtube,
    "Instagram": process_instagram,
    "Facebook": process_facebook,
    "Twitter/X": download_twitter_media,
    "Adult": process_adult,
}

class DownloadError(Exception):
    """Custom exception for download errors"""
    pass

async def send_message(chat_id, text, parse_mode="HTML"):
    """
    Sends a message asynchronously with error handling.
    """
    try:
        await bot.send_message(chat_id, text, parse_mode=parse_mode)
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        # Attempt to send without parse mode if parsing fails
        if parse_mode:
            try:
                await bot.send_message(chat_id, text, parse_mode=None)
            except Exception as e2:
                logger.error(f"Failed to send message without parse mode: {e2}")

def detect_platform(url):
    """
    Detects the platform based on URL patterns.
    Returns None if no matching platform is found.
    """
    if not url:
        return None
    
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None

async def upload_to_mega(file_path, filename):
    """
    Uploads a file to Mega.nz and returns a shareable link.
    Includes enhanced error handling and logging.
    """
    try:
        # Verify file exists
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None

        # Initialize Mega client
        mega = Mega()
        logger.info("Attempting to login to Mega.nz...")
        
        if not MEGA_EMAIL or not MEGA_PASSWORD:
            logger.error("Mega.nz credentials not found in environment variables")
            return None
            
        try:
            m = mega.login(MEGA_EMAIL, MEGA_PASSWORD)
            if not m:
                logger.error("Mega.nz login failed - no session returned")
                return None
            logger.info("Successfully logged in to Mega.nz")
            
        except Exception as login_error:
            logger.error(f"Mega.nz authentication failed: {login_error}")
            return None
        
        # Create upload folder
        try:
            folder_name = "telegram_uploads"
            folders = m.get_folders()
            
            folder_id = None
            for f in folders.items():
                if f[1]['a']['n'] == folder_name:
                    folder_id = f[0]
                    break
            
            if not folder_id:
                folder_id = m.create_folder(folder_name)
                logger.info(f"Created new folder on Mega: {folder_name}")

            # Upload file
            logger.info(f"Uploading file: {filename}")
            file = m.upload(file_path, dest=folder_id)
            
            if not file:
                raise DownloadError("Upload failed - no file object returned")
                
            # Get shareable link
            link = m.get_upload_link(file)
            if not link:
                raise DownloadError("Failed to get upload link")
                
            logger.info(f"Successfully uploaded to Mega.nz: {link}")
            return link
            
        except Exception as upload_error:
            logger.error(f"Error during upload process: {upload_error}")
            return None

    except ImportError:
        logger.error("Mega.py library not installed. Run: pip install mega.py")
        return None
    except Exception as e:
        logger.error(f"Unexpected Mega.nz upload error: {e}")
        return None

async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    """
    Handles video/audio download and sends it to Telegram or Mega.nz.
    Includes improved error handling and progress updates.
    """
    try:
        # Determine request type and send initial status
        request_type = (
            "Audio Download" if is_audio else
            "Video Trimming" if is_video_trim else
            "Audio Trimming" if is_audio_trim else
            "Video Download"
        )

        await send_message(message.chat.id, f"📥 **Processing your {request_type.lower()}...**")
        logger.info(f"Processing URL: {url}, Type: {request_type}")

        # Validate URL and platform
        if not url:
            await send_message(message.chat.id, "⚠️ **Please provide a valid URL.**")
            return

        platform = detect_platform(url)
        if not platform:
            await send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        # Process the request based on type
        try:
            if is_video_trim:
                result = await process_video_trim(url, start_time, end_time)
                file_paths = [result[0]] if result and result[0] else []
                file_size = result[1] if result else None
                download_url = None
            elif is_audio_trim:
                result = await process_audio_trim(url, start_time, end_time)
                file_paths = [result[0]] if result and result[0] else []
                file_size = result[1] if result else None
                download_url = None
            elif is_audio:
                result = await extract_audio_ffmpeg(url)
                if isinstance(result, tuple):
                    file_paths = [result[0]] if result[0] else []
                    file_size = result[1] if len(result) > 1 else None
                    download_url = None
                else:
                    file_paths = [result] if result else []
                    file_size = None
                    download_url = None
            else:
                # Handle platform-specific downloads
                result = await PLATFORM_HANDLERS[platform](url)
                
                # Normalize result format
                if isinstance(result, tuple) and len(result) >= 3:
                    file_paths, file_size, download_url = result
                    file_paths = [file_paths] if not isinstance(file_paths, list) else file_paths
                elif isinstance(result, tuple) and len(result) == 2:
                    file_paths, file_size = result
                    download_url = None
                    file_paths = [file_paths] if not isinstance(file_paths, list) else file_paths
                else:
                    file_paths = [result] if result and not isinstance(result, list) else result or []
                    file_size = None
                    download_url = None

            # Process each downloaded file
            if not file_paths:
                raise DownloadError("No media found")

            for file_path in file_paths:
                if not file_path or not os.path.exists(file_path):
                    continue

                try:
                    # Get actual file size
                    file_size = os.path.getsize(file_path)

                    # Handle large files
                    if file_size > TELEGRAM_FILE_LIMIT:
                        filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                        mega_link = await upload_to_mega(file_path, filename)

                        if mega_link:
                            await send_message(
                                message.chat.id,
                                f"⚠️ **File too large for Telegram.**\n📥 [Download from Mega.nz]({mega_link})",
                                parse_mode="Markdown"
                            )
                        elif download_url:
                            await send_message(
                                message.chat.id,
                                f"⚠️ **File too large for Telegram.**\n📥 [Direct download]({download_url})",
                                parse_mode="Markdown"
                            )
                        else:
                            await send_message(message.chat.id, "❌ **File too large and upload failed.**")
                    else:
                        # Send file through Telegram
                        async with aiofiles.open(file_path, "rb") as file:
                            file_content = await file.read()
                            if is_audio or is_audio_trim:
                                await bot.send_audio(message.chat.id, file_content, timeout=600)
                            else:
                                await bot.send_video(message.chat.id, file_content, 
                                                   supports_streaming=True, timeout=600)

                except Exception as send_error:
                    logger.error(f"Error sending file: {send_error}")
                    if "413" in str(send_error):
                        # Attempt Mega.nz upload as fallback
                        mega_link = await upload_to_mega(file_path, 
                                                       f"{message.chat.id}_{os.path.basename(file_path)}")
                        if mega_link:
                            await send_message(
                                message.chat.id,
                                f"⚠️ **File too large for Telegram.**\n📥 [Download from Mega.nz]({mega_link})",
                                parse_mode="Markdown"
                            )
                        else:
                            await send_message(message.chat.id, "❌ **File too large and upload failed.**")
                    else:
                        await send_message(message.chat.id, f"❌ **Error sending file: {str(send_error)}**")

                finally:
                    # Cleanup
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            logger.info(f"Cleaned up file: {file_path}")
                    except Exception as cleanup_error:
                        logger.error(f"Failed to clean up file {file_path}: {cleanup_error}")

            # Final cleanup
            gc.collect()

        except Exception as process_error:
            logger.error(f"Error processing {request_type}: {process_error}")
            await send_message(message.chat.id, f"❌ **Error processing {request_type.lower()}: {str(process_error)}**")

    except Exception as e:
        logger.error(f"Comprehensive error in process_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred: {str(e)}**")

async def process_image_download(message, url):
    """
    Handles image download and sends it to Telegram or Mega.nz.
    Includes improved error handling and progress updates.
    """
    try:
        await send_message(message.chat.id, "🖼️ Processing Instagram image...")
        logger.info(f"Processing Instagram image URL: {url}")

        result = await process_instagram_image(url)

        # Normalize result format
        if isinstance(result, list):
            file_paths = result
        elif isinstance(result, tuple) and len(result) >= 2:
            file_paths = result[0] if isinstance(result[0], list) else [result[0]]
        else:
            file_paths = [result] if result else []

        if not file_paths:
            await send_message(message.chat.id, "❌ **No images found.**")
            return

        # Process each image
        for file_path in file_paths:
            if not file_path or not os.path.exists(file_path):
                continue

            try:
                file_size = os.path.getsize(file_path)

                if file_size > TELEGRAM_FILE_LIMIT:
                    mega_link = await upload_to_mega(file_path, 
                                                   f"{message.chat.id}_{os.path.basename(file_path)}")
                    if mega_link:
                        await send_message(
                            message.chat.id,
                            f"⚠️ **Image too large for Telegram.**\n📥 [Download from Mega.nz]({mega_link})",
                            parse_mode="Markdown"
                        )
                    else:
                        await send_message(message.chat.id, "❌ **Image upload failed.**")
                else:
                    async with aiofiles.open(file_path, "rb") as file:
                        file_content = await file.read()
                        await bot.send_photo(message.chat.id, file_content, timeout=60)

            except Exception as send_error:
                logger.error(f"Error sending image: {send_error}")
                await send_message(message.chat.id, f"❌ **Error sending image: {str(send_error)}**")

            finally:
                # Cleanup
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Cleaned up image: {file_path}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up image {file_path}: {cleanup_error}")

        await send_message(message.chat.id, "✅ **Images processed successfully!**")

    except Exception as e:
        logger.error(f"Error in process_image_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred: {str(e)}**")

async def worker():
    """Worker function for parallel processing of downloads."""
    while True:
        try:
            task = await download_queue.get()

            if len(task) == 2:
                message, url = task
                await process_image_download(message, url)
            else:
                message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time = task
                await process_download(message, url, is_audio, is_video_trim, is_audio_trim, 
                                    start_time, end_time)

        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
        finally:
            download_queue.task_done()

# Command handlers
@bot.message_handler(commands=["start", "help"])
async def send_welcome(message):
    """Sends welcome message with bot instructions."""
    welcome_text = (
        "🤖 Media Download Bot 🤖\n\n"
        "I can help you download media from various platforms:\n"
        "• YouTube\n• Instagram\n• Facebook\n• Twitter/X\n\n"
        "Commands:\n"
        "• Send a direct URL to download video\n"
        "• /audio <URL> - Extract full audio from video\n"
        "• /image <URL> - Download Instagram images\n"
        "• /trim <URL> <Start Time> <End Time> - Trim video segment\n"
        "• /trimAudio <URL> <Start Time> <End Time> - Extract audio segment\n\n"
        "Examples:\n"
        "• /image https://instagram.com/p/example\n"
        "• /trim https://youtube.com/watch?v=example 00:01:00 00:02:30\n"
        "• /trimAudio https://youtube.com/watch?v=example 00:01:00 00:02:30"
    )
    await bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=["audio"])
async def handle_audio_request(message):
    """Handles audio extraction requests."""
    url = message.text.replace("/audio", "").strip()
    if not url:
        await send_message(message.chat.id, "⚠️ Please provide a URL.")
        return
    await download_queue.put((message, url, True, False, False, None, None))
    await send_message(message.chat.id, "🎵 Added to audio extraction queue!")

@bot.message_handler(commands=["image"])
async def handle_image_request(message):
    """Handles Instagram image download requests."""
    url = message.text.replace("/image", "").strip()
    if not url:
        await send_message(message.chat.id, "⚠️ Please provide an Instagram image URL.")
        return

    if not PLATFORM_PATTERNS["Instagram"].search(url):
        await send_message(message.chat.id, "⚠️ **This command only works with Instagram URLs.**")
        return

    await download_queue.put((message, url))
    await send_message(message.chat.id, "🖼️ **Added to image download queue!**")

@bot.message_handler(commands=["trim"])
async def handle_video_trim_request(message):
    """Handles video trimming requests."""
    match = re.search(r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", message.text)
    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format. Use: /trim <URL> <Start Time (HH:MM:SS)> <End Time (HH:MM:SS)>"
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
            "⚠️ Invalid format. Use: /trimAudio <URL> <Start Time (HH:MM:SS)> <End Time (HH:MM:SS)>"
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
    await send_message(message.chat.id, "🎬 Added to video download queue!")

async def main():
    """Runs the bot and initializes worker processes."""
    try:
        # Initialize workers
        num_workers = min(int(MAX_WORKERS), os.cpu_count() or 1)
        workers = [asyncio.create_task(worker()) for _ in range(num_workers)]
        logger.info(f"Started {num_workers} workers")

        # Start bot
        logger.info("Starting bot polling...")
        await bot.infinity_polling(timeout=60)

    except Exception as e:
        logger.error(f"Bot initialization error: {e}", exc_info=True)
    finally:
        # Cleanup
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())