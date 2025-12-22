import os
import gc
import logging
import asyncio
import aiofiles
import re
import time
import psutil
from datetime import datetime, timezone
from mega import Mega
from telebot.async_telebot import AsyncTeleBot
from asyncio import Semaphore
from config import DOWNLOAD_DIR, INSTAGRAM_PASSWORD, INSTAGRAM_USERNAME

# Import local modules
from config import (
    API_TOKEN,
    TELEGRAM_FILE_LIMIT,
    MEGA_EMAIL,
    MEGA_PASSWORD,
    DEFAULT_ADMIN,
    ADMIN_IDS
)
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import process_video_trim, process_audio_trim
from handlers.image_handlers import process_instagram_image
from utils.logger import setup_logging
from utils.instagram_cookies import auto_refresh_cookies

# Constants
MAX_MEMORY_USAGE = 500 * 1024 * 1024  # 500MB
MAX_CONCURRENT_DOWNLOADS = 2
CLEANUP_INTERVAL = 300  # 5 minutes

# Logging setup
logger = setup_logging(logging.DEBUG)

# Async Telegram bot
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()
download_semaphore = Semaphore(MAX_CONCURRENT_DOWNLOADS)

# MEGA client
mega = None

# Active downloads
active_downloads = set()

# Regex patterns
PLATFORM_PATTERNS = {
    "YouTube": re.compile(r"(youtube\.com|youtu\.be)"),
    "Instagram": re.compile(r"instagram\.com"),
    "Facebook": re.compile(r"facebook\.com"),
    "Twitter/X": re.compile(r"(x\.com|twitter\.com)"),
    "Adult": re.compile(r"(pornhub\.com|xvideos\.com|redtube\.com|xhamster\.com|xnxx\.com)"),
}

# Handlers
PLATFORM_HANDLERS = {
    "YouTube": process_youtube,
    "Instagram": process_instagram,
    "Facebook": process_facebook,
    "Twitter/X": download_twitter_media,
    "Adult": process_adult,
}

def get_current_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def detect_platform(url):
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None

async def check_memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss < MAX_MEMORY_USAGE

async def cleanup_files():
    while True:
        try:
            temp_dir = DOWNLOAD_DIR
            if os.path.exists(temp_dir):
                for filename in os.listdir(temp_dir):
                    filepath = os.path.join(temp_dir, filename)
                    try:
                        if os.path.isfile(filepath) and time.time() - os.path.getctime(filepath) > 3600:
                            os.remove(filepath)
                    except Exception as e:
                        logger.error(f"[{get_current_utc()}] Cleanup error: {e}")
            gc.collect()
            await asyncio.sleep(CLEANUP_INTERVAL)
        except Exception as e:
            logger.error(f"[{get_current_utc()}] Cleanup task failed: {e}")
            await asyncio.sleep(60)

async def send_message(chat_id, text):
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"[{get_current_utc()}] Error sending message: {e}")

async def get_mega_client():
    global mega
    if mega is None:
        try:
            m = Mega()
            mega = await asyncio.to_thread(m.login, MEGA_EMAIL, MEGA_PASSWORD)
            logger.info(f"[{get_current_utc()}] MEGA client logged in")
        except Exception as e:
            logger.error(f"[{get_current_utc()}] MEGA login failed: {e}")
            return None
    return mega

async def upload_to_mega(file_path):
    try:
        mega_client = await get_mega_client()
        if not mega_client:
            return None
        file = await asyncio.to_thread(mega_client.upload, file_path)
        link = await asyncio.to_thread(mega_client.get_upload_link, file)
        return link
    except Exception as e:
        logger.error(f"[{get_current_utc()}] MEGA upload failed: {e}")
        return None

async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    download_id = f"{message.chat.id}_{int(time.time())}"
    active_downloads.add(download_id)
    try:
        if not await check_memory_usage():
            await send_message(message.chat.id, "⚠️ Server under high load. Try later.")
            return

        async with download_semaphore:
            request_type = "Video"
            if is_audio: request_type = "Audio"
            elif is_video_trim: request_type = "Video Trim"
            elif is_audio_trim: request_type = "Audio Trim"

            await send_message(message.chat.id, f"📥 Processing {request_type}...")

            platform = detect_platform(url)
            if not platform:
                await send_message(message.chat.id, "⚠️ Unsupported URL.")
                return

            # Download/Process
            file_paths = []
            file_size = None
            if is_video_trim:
                result = await process_video_trim(url, start_time, end_time)
                file_paths = [result[0]] if result else []
                file_size = result[1] if result else None
            elif is_audio_trim:
                result = await process_audio_trim(url, start_time, end_time)
                file_paths = [result[0]] if result else []
                file_size = result[1] if result else None
            elif is_audio:
                result = await extract_audio_ffmpeg(url)
                file_paths = [result[0]] if isinstance(result, tuple) else [result]
                file_size = result[1] if isinstance(result, tuple) and len(result) > 1 else None
            else:
                result = await PLATFORM_HANDLERS[platform](url)
                if isinstance(result, tuple):
                    file_paths = result[0] if isinstance(result[0], list) else [result[0]]
                    file_size = result[1] if len(result) > 1 else None
                else:
                    file_paths = [result] if result else []

            if not file_paths:
                await send_message(message.chat.id, "❌ Download failed.")
                return

            for file_path in file_paths:
                if not file_path or not os.path.exists(file_path):
                    continue
                file_size = file_size or os.path.getsize(file_path)
                if file_size > TELEGRAM_FILE_LIMIT:
                    mega_link = await upload_to_mega(file_path)
                    if mega_link:
                        await send_message(message.chat.id, f"✅ Uploaded to MEGA:\n{mega_link}")
                    else:
                        await send_message(message.chat.id, "❌ Upload failed.")
                else:
                    async with aiofiles.open(file_path, 'rb') as f:
                        content = await f.read()
                        if is_audio or is_audio_trim:
                            await bot.send_audio(message.chat.id, content)
                        else:
                            await bot.send_video(message.chat.id, content, supports_streaming=True)

                if os.path.exists(file_path):
                    os.remove(file_path)
    except Exception as e:
        logger.error(f"[{get_current_utc()}] Error: {e}")
        await send_message(message.chat.id, f"❌ Error: {e}")
    finally:
        active_downloads.discard(download_id)
        gc.collect()

async def process_image_download(message, url):
    try:
        await send_message(message.chat.id, "🖼️ Processing Instagram image...")
        result = await process_instagram_image(url)
        file_paths = []
        if isinstance(result, list):
            file_paths = result
        elif isinstance(result, tuple) and len(result) >= 2:
            file_paths = result[0] if isinstance(result[0], list) else [result[0]]
        else:
            file_paths = [result] if result else []

        if not file_paths:
            await send_message(message.chat.id, "❌ No images found.")
            return

        for file_path in file_paths:
            if not file_path or not os.path.exists(file_path):
                continue
            file_size = os.path.getsize(file_path)
            if file_size > TELEGRAM_FILE_LIMIT:
                mega_link = await upload_to_mega(file_path)
                if mega_link:
                    await send_message(message.chat.id, f"⚠️ Image too large, download here:\n{mega_link}")
            else:
                async with aiofiles.open(file_path, 'rb') as f:
                    await bot.send_photo(message.chat.id, await f.read())
            if os.path.exists(file_path):
                os.remove(file_path)
        await send_message(message.chat.id, "✅ Image(s) downloaded successfully!")
    except Exception as e:
        logger.error(f"Image download error: {e}")
        await send_message(message.chat.id, f"❌ Error: {e}")

# Worker
async def worker():
    while True:
        task = await download_queue.get()
        if len(task) == 2:
            message, url = task
            await process_image_download(message, url)
        else:
            message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time = task
            await process_download(message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time)
        download_queue.task_done()

# Bot commands
@bot.message_handler(commands=["start", "help"])
async def send_welcome(message):
    await send_message(message.chat.id, "🤖 Media Download Bot\nSend URL or use commands: /audio, /image, /trim, /trimAudio")

@bot.message_handler(commands=["audio"])
async def handle_audio_request(message):
    url = message.text.replace("/audio", "").strip()
    if url:
        await download_queue.put((message, url, True, False, False, None, None))
        await send_message(message.chat.id, "🎵 Added to audio queue!")

@bot.message_handler(commands=["image"])
async def handle_image_request(message):
    url = message.text.replace("/image", "").strip()
    if url:
        await download_queue.put((message, url))
        await send_message(message.chat.id, "🖼️ Added to image queue!")

@bot.message_handler(commands=["trim"])
async def handle_video_trim_request(message):
    match = re.search(r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", message.text)
    if match:
        url, start_time, end_time = match.groups()
        await download_queue.put((message, url, False, True, False, start_time, end_time))
        await send_message(message.chat.id, "✂️ Added to video trimming queue!")

@bot.message_handler(commands=["trimAudio"])
async def handle_audio_trim_request(message):
    match = re.search(r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", message.text)
    if match:
        url, start_time, end_time = match.groups()
        await download_queue.put((message, url, False, False, True, start_time, end_time))
        await send_message(message.chat.id, "✂️🎵 Added to audio trim queue!")

@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    url = message.text.strip()
    await download_queue.put((message, url, False, False, False, None, None))
    await send_message(message.chat.id, "🎬 Added to download queue!")

# Main runner
async def main():
    # Background tasks
    asyncio.create_task(auto_refresh_cookies())
    asyncio.create_task(cleanup_files())
    # Workers
    num_workers = min(3, os.cpu_count() or 1)
    for _ in range(num_workers):
        asyncio.create_task(worker())
    # Start bot
    await bot.infinity_polling(timeout=30)

if __name__ == "__main__":
    asyncio.run(main())