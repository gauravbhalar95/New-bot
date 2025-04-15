import os
import gc
import logging
import asyncio
import aiofiles
import re
import signal
import sys
import time
from mega import Mega
from telebot.async_telebot import AsyncTeleBot
from contextlib import contextmanager
from datetime import datetime

# Import local modules
from config import API_TOKEN, TELEGRAM_FILE_LIMIT, MEGA_EMAIL, MEGA_PASSWORD
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import process_video_trim, process_audio_trim
from handlers.image_handlers import process_instagram_image
from utils.logger import setup_logging

# Constants
LOCK_FILE = '/tmp/telegram_bot.lock'
MAX_RETRIES = 3
RETRY_DELAY = 5
DOWNLOAD_DIR = 'downloads'

# Logging setup
logger = setup_logging(logging.DEBUG)

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

def check_requirements():
    """Check if all required external programs are installed."""
    required_programs = ['ffmpeg']
    missing_programs = []
    
    for program in required_programs:
        if os.system(f"which {program} > /dev/null") != 0:
            missing_programs.append(program)
    
    if missing_programs:
        logger.error(f"Required programs not installed: {', '.join(missing_programs)}")
        sys.exit(1)

@contextmanager
def pid_lock():
    """Context manager for handling PID lock file."""
    try:
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, 0)
                logger.error(f"Bot is already running with PID {pid}")
                sys.exit(1)
            except OSError:
                os.remove(LOCK_FILE)
        
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        
        yield
    finally:
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except Exception as e:
            logger.error(f"Error removing lock file: {e}")

async def shutdown(signal, loop):
    """Cleanup function to be called before shutdown."""
    logger.info(f"Received exit signal {signal.name}")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    
    [task.cancel() for task in tasks]
    logger.info(f"Cancelling {len(tasks)} outstanding tasks")
    
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()
    
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
    
    logger.info("Shutdown complete")

def create_bot():
    """Create bot instance with error handling."""
    try:
        return AsyncTeleBot(API_TOKEN, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to create bot instance: {e}")
        sys.exit(1)

def setup_mega():
    """Setup MEGA client with retries."""
    for attempt in range(MAX_RETRIES):
        try:
            mega = Mega()
            m = mega.login(MEGA_EMAIL, MEGA_PASSWORD)
            logger.info("Successfully logged in to MEGA")
            return m
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"MEGA login attempt {attempt + 1} failed: {e}. Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Failed to login to MEGA after {MAX_RETRIES} attempts: {e}")
                return None

bot = create_bot()
download_queue = asyncio.Queue()
m = setup_mega()

async def send_message(chat_id, text):
    """Sends a message asynchronously with retry mechanism."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            await bot.send_message(chat_id, text)
            return
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to send message after {max_retries} attempts: {e}")
            else:
                await asyncio.sleep(1)

def detect_platform(url):
    """Detects the platform based on URL patterns."""
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None

async def upload_to_mega(file_path, filename):
    """Uploads a file to MEGA and returns a shareable link."""
    if not m:
        logger.error("MEGA client not initialized")
        return None

    try:
        folder = 'telegram_uploads'
        folders = m.get_folder_path_by_name(folder)
        if not folders:
            folder_node = m.create_folder(folder)
        else:
            folder_node = folders[0]

        file = m.upload(file_path, folder_node)
        file_node = m.get_node_by_handle(file)
        share_link = m.get_link(file_node)
        
        return share_link

    except Exception as e:
        logger.error(f"MEGA upload error: {e}")
        return None

async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    """Handles video/audio download and sends it to Telegram or MEGA."""
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

        platform = detect_platform(url)
        if not platform:
            await send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        if is_video_trim:
            file_path, file_size = await process_video_trim(url, start_time, end_time)
            download_url = None
            file_paths = [file_path] if file_path else []
        elif is_audio_trim:
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
                if "/reel/" in url or "/tv/" in url:
                    result = await process_instagram(url)
                else:
                    result = await process_instagram_image(url)
            else:
                result = await PLATFORM_HANDLERS[platform](url)

            if isinstance(result, tuple) and len(result) >= 3:
                file_paths, file_size, download_url = result
                if not isinstance(file_paths, list):
                    file_paths = [file_paths] if file_paths else []
            elif isinstance(result, tuple) and len(result) == 2:
                file_paths, file_size = result
                download_url = None
                if not isinstance(file_paths, list):
                    file_paths = [file_paths] if file_paths else []
            else:
                file_paths = result if isinstance(result, list) else [result] if result else []
                file_size = None
                download_url = None

        if not file_paths or all(not path for path in file_paths):
            logger.warning("No valid file paths returned from platform handler")
            await send_message(message.chat.id, "❌ **Download failed. No media found.**")
            return

        for file_path in file_paths:
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"File path does not exist: {file_path}")
                continue

            if file_size is None:
                file_size = os.path.getsize(file_path)

            if file_size > TELEGRAM_FILE_LIMIT:
                filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                logger.info(f"File too large for Telegram: {file_size} bytes. Using MEGA.")
                mega_link = await upload_to_mega(file_path, filename)

                if mega_link:
                    await send_message(
                        message.chat.id,
                        f"⚠️ **File too large for Telegram.**\n📥 [Download from MEGA]({mega_link})"
                    )
                else:
                    if download_url:
                        await send_message(
                            message.chat.id,
                            f"⚠️ **File too large for Telegram.**\n📥 [Download here]({download_url})"
                        )
                    else:
                        await send_message(message.chat.id, "❌ **Download failed.**")
            else:
                try:
                    async with aiofiles.open(file_path, "rb") as file:
                        file_content = await file.read()
                        if is_audio or is_audio_trim:
                            await bot.send_audio(message.chat.id, file_content, timeout=600)
                        else:
                            await bot.send_video(message.chat.id, file_content, supports_streaming=True, timeout=600)
                except Exception as send_error:
                    logger.error(f"Error sending file to Telegram: {send_error}")
                    if "413" in str(send_error):
                        filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                        mega_link = await upload_to_mega(file_path, filename)
                        if mega_link:
                            await send_message(
                                message.chat.id,
                                f"⚠️ **File too large for Telegram.**\n📥 [Download from MEGA]({mega_link})"
                            )
                        else:
                            await send_message(message.chat.id, "❌ **File too large and MEGA upload failed.**")
                    else:
                        await send_message(message.chat.id, f"❌ **Error sending file: {str(send_error)}**")

            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Cleaned up file: {file_path}")
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up file {file_path}: {cleanup_error}")

        gc.collect()

    except Exception as e:
        logger.error(f"Comprehensive error in process_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

async def process_image_download(message, url):
    """Handles image download and sends it to Telegram or MEGA."""
    try:
        await send_message(message.chat.id, "🖼️ Processing Instagram image...")
        logger.info(f"Processing Instagram image URL: {url}")

        try:
            result = await process_instagram_image(url)

            if isinstance(result, list):
                file_paths = result
            elif isinstance(result, tuple) and len(result) >= 2:
                file_paths = result[0] if isinstance(result[0], list) else [result[0]]
            else:
                file_paths = [result] if result else []

            if not file_paths or all(not path for path in file_paths):
                logger.warning("No valid image paths returned from Instagram handler")
                await send_message(message.chat.id, "❌ **Download failed. No images found.**")
                return

            for file_path in file_paths:
                if not file_path or not os.path.exists(file_path):
                    logger.warning(f"Image path does not exist: {file_path}")
                    continue

                file_size = os.path.getsize(file_path)

                if file_size > TELEGRAM_FILE_LIMIT:
                    filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                    mega_link = await upload_to_mega(file_path, filename)

                    if mega_link:
                        await send_message(
                            message.chat.id,
                            f"⚠️ **Image too large for Telegram.**\n📥 [Download from MEGA]({mega_link})"
                        )
                    else:
                        await send_message(message.chat.id, "❌ **Image download failed.**")
                else:
                    try:
                        async with aiofiles.open(file_path, "rb") as file:
                            file_content = await file.read()
                            await bot.send_photo(message.chat.id, file_content, timeout=60)
                    except Exception as send_error:
                        logger.error(f"Error sending image to Telegram: {send_error}")
                        await send_message(message.chat.id, f"❌ **Error sending image: {str(send_error)}**")

                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Cleaned up image file: {file_path}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up image file {file_path}: {cleanup_error}")

            await send_message(message.chat.id, "✅ **Instagram image(s) downloaded successfully!**")

        except Exception as e:
            logger.error(f"Error processing Instagram image: {e}", exc_info=True)
            await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

    except Exception as e:
        logger.error(f"Comprehensive error in process_image_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

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
                await process_download(message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Worker error: {e}")
        finally:
            download_queue.task_done()

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
    """Handles audio extraction requests for all platforms."""
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
        await send_message(message.chat.id, "⚠️ **This command only works with Instagram image URLs.**")
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
            "⚠️ Invalid format. Please send: /trim <URL> <Start Time (HH:MM:SS)> <End Time (HH:MM:SS)>"
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
            "⚠️ Invalid format. Please send: /trimAudio <URL> <Start Time (HH:MM:SS)> <End Time (HH:MM:SS)>"
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
    # Create downloads directory if it doesn't exist
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    # Check requirements
    check_requirements()
    
    loop = asyncio.get_running_loop()
    
    # Add signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(s, loop))
        )
    
    # Start worker tasks
    num_workers = min(3, os.cpu_count() or 1)
    worker_tasks = [asyncio.create_task(worker()) for _ in range(num_workers)]
    
    try:
        with pid_lock():
            logger.info(f"Starting bot with PID {os.getpid()}")
            await bot.infinity_polling(timeout=30, restart_on_exception=True)
    except Exception as e:
        logger.error(f"Bot polling error: {e}")
    finally:
        # Cancel worker tasks
        for task in worker_tasks:
            task.cancel()
        
        # Wait for workers to complete
        await asyncio.gather(*worker_tasks, return_exceptions=True)
        
        # Final cleanup
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        # Cleanup on exit
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)