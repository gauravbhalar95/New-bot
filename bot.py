import os
import gc
import logging
import asyncio
import aiofiles
import aiohttp
import re
import tempfile
from mega import Mega
from telebot.async_telebot import AsyncTeleBot
from contextlib import asynccontextmanager

# Import local modules
from config import (
    API_TOKEN, 
    TELEGRAM_FILE_LIMIT, 
    MEGA_EMAIL, 
    MEGA_PASSWORD,
    MAX_CONCURRENT_DOWNLOADS,
    CHUNK_SIZE,
    MAX_RETRIES,
    TEMP_DIR,
    LOGGING_LEVEL
)

# Import handlers
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import process_video_trim, process_audio_trim
from handlers.image_handlers import process_instagram_image
from utils.logger import setup_logging

# Constants and configurations
os.makedirs(TEMP_DIR, exist_ok=True)
logger = setup_logging(LOGGING_LEVEL)
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
processing_tasks = set()

# Platform patterns
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

class MEGAHandler:
    def __init__(self):
        self.client = None
        self.retries = 0
        self.lock = asyncio.Lock()

    async def get_client(self):
        async with self.lock:
            if self.client is None:
                for attempt in range(MAX_RETRIES):
                    try:
                        mega = Mega()
                        self.client = mega.login(MEGA_EMAIL, MEGA_PASSWORD)
                        logger.info("Successfully connected to MEGA")
                        break
                    except Exception as e:
                        logger.error(f"MEGA login attempt {attempt + 1} failed: {e}")
                        if attempt == MAX_RETRIES - 1:
                            raise
                        await asyncio.sleep(2 ** attempt)
            return self.client

    async def upload_file(self, file_path, filename):
        try:
            client = await self.get_client()
            folder = client.find('telegram_uploads')
            if not folder:
                folder = client.create_folder('telegram_uploads')

            uploaded_file = client.upload(file_path, folder[0])
            file_node = client.get_id_from_obj(uploaded_file)
            return client.get_link(file_node)
        except Exception as e:
            logger.error(f"MEGA upload error: {e}")
            return None

mega_handler = MEGAHandler()

@asynccontextmanager
async def temp_file():
    """Context manager for temporary file handling"""
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, dir=TEMP_DIR) as tmp:
            temp_path = tmp.name
            yield temp_path
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.error(f"Failed to remove temp file {temp_path}: {e}")

async def send_message(chat_id, text, parse_mode="HTML"):
    """Send message with error handling"""
    try:
        await bot.send_message(chat_id, text, parse_mode=parse_mode)
    except Exception as e:
        logger.error(f"Error sending message: {e}")

async def stream_download(url, file_path):
    """Stream download files in chunks"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Download failed with status {response.status}")
            
            async with aiofiles.open(file_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                    await f.write(chunk)
                    await asyncio.sleep(0)

def detect_platform(url):
    """Detect platform from URL"""
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None

async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    """Process download with memory optimization"""
    task = asyncio.current_task()
    processing_tasks.add(task)
    
    try:
        async with download_semaphore:
            request_type = ("Audio" if is_audio else "Video Trim" if is_video_trim 
                          else "Audio Trim" if is_audio_trim else "Video") + " Download"
            
            await send_message(message.chat.id, f"📥 **Processing your {request_type.lower()}...**")
            logger.info(f"Processing URL: {url}, Type: {request_type}")

            platform = detect_platform(url)
            if not platform:
                await send_message(message.chat.id, "⚠️ **Unsupported URL.**")
                return

            async with temp_file() as temp_path:
                try:
                    if is_video_trim or is_audio_trim:
                        handler_func = process_video_trim if is_video_trim else process_audio_trim
                        result = await handler_func(url, start_time, end_time)
                    elif is_audio:
                        result = await extract_audio_ffmpeg(url)
                    else:
                        handler = PLATFORM_HANDLERS.get(platform)
                        if not handler:
                            await send_message(message.chat.id, "❌ **Unsupported platform.**")
                            return
                        result = await handler(url)

                    if not result:
                        await send_message(message.chat.id, "❌ **Download failed.**")
                        return

                    file_path = result[0] if isinstance(result, tuple) else result
                    if not os.path.exists(file_path):
                        await send_message(message.chat.id, "❌ **File processing failed.**")
                        return

                    file_size = os.path.getsize(file_path)
                    if file_size > TELEGRAM_FILE_LIMIT:
                        filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                        mega_link = await mega_handler.upload_file(file_path, filename)
                        
                        if mega_link:
                            await send_message(
                                message.chat.id,
                                f"⚠️ **File too large for Telegram.**\n📥 [Download from MEGA]({mega_link})",
                                parse_mode="Markdown"
                            )
                        else:
                            await send_message(message.chat.id, "❌ **Upload to MEGA failed.**")
                    else:
                        async with aiofiles.open(file_path, 'rb') as file:
                            file_content = await file.read()
                            if is_audio or is_audio_trim:
                                await bot.send_audio(message.chat.id, file_content, timeout=600)
                            else:
                                await bot.send_video(
                                    message.chat.id,
                                    file_content,
                                    supports_streaming=True,
                                    timeout=600
                                )

                finally:
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        logger.error(f"Error cleaning up file: {e}")

    except Exception as e:
        logger.error(f"Error in process_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{str(e)}`")
    finally:
        processing_tasks.discard(task)
        gc.collect()

async def process_image_download(message, url):
    """Process image download with memory optimization"""
    task = asyncio.current_task()
    processing_tasks.add(task)
    
    try:
        async with download_semaphore:
            await send_message(message.chat.id, "🖼️ Processing Instagram image...")
            logger.info(f"Processing Instagram image URL: {url}")

            async with temp_file() as temp_path:
                try:
                    result = await process_instagram_image(url)
                    if not result:
                        await send_message(message.chat.id, "❌ **Download failed.**")
                        return

                    file_paths = result if isinstance(result, list) else [result]
                    for file_path in file_paths:
                        if not os.path.exists(file_path):
                            continue

                        file_size = os.path.getsize(file_path)
                        if file_size > TELEGRAM_FILE_LIMIT:
                            filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                            mega_link = await mega_handler.upload_file(file_path, filename)
                            
                            if mega_link:
                                await send_message(
                                    message.chat.id,
                                    f"⚠️ **Image too large for Telegram.**\n📥 [Download from MEGA]({mega_link})",
                                    parse_mode="Markdown"
                                )
                            else:
                                await send_message(message.chat.id, "❌ **Upload to MEGA failed.**")
                        else:
                            async with aiofiles.open(file_path, 'rb') as file:
                                file_content = await file.read()
                                await bot.send_photo(message.chat.id, file_content, timeout=60)

                finally:
                    for file_path in file_paths:
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                        except Exception as e:
                            logger.error(f"Error cleaning up file: {e}")

    except Exception as e:
        logger.error(f"Error in process_image_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{str(e)}`")
    finally:
        processing_tasks.discard(task)
        gc.collect()

async def cleanup_temp_files():
    """Periodic cleanup of temporary files"""
    while True:
        try:
            for filename in os.listdir(TEMP_DIR):
                file_path = os.path.join(TEMP_DIR, filename)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logger.error(f"Error cleaning up {file_path}: {e}")
            await asyncio.sleep(3600)
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
            await asyncio.sleep(3600)

async def worker():
    """Worker for processing download queue"""
    while True:
        task = await download_queue.get()
        try:
            if len(task) == 2:
                message, url = task
                await process_image_download(message, url)
            else:
                message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time = task
                await process_download(message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time)
        except Exception as e:
            logger.error(f"Worker error: {e}")
        finally:
            download_queue.task_done()

# Command handlers
@bot.message_handler(commands=["start", "help"])
async def send_welcome(message):
    """Send welcome message"""
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
    """Handle audio extraction"""
    url = message.text.replace("/audio", "").strip()
    if not url:
        await send_message(message.chat.id, "⚠️ Please provide a URL.")
        return
    await download_queue.put((message, url, True, False, False, None, None))
    await send_message(message.chat.id, "🎵 Added to audio extraction queue!")

@bot.message_handler(commands=["image"])
async def handle_image_request(message):
    """Handle Instagram image download"""
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
    """Handle video trimming"""
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
    """Handle audio trimming"""
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
    """Handle general video download"""
    url = message.text.strip()
    await download_queue.put((message, url, False, False, False, None, None))
    await send_message(message.chat.id, "🎬 Added to video download queue!")

async def main():
    """Main function to run the bot"""
    num_workers = min(2, os.cpu_count() or 1)
    workers = [asyncio.create_task(worker()) for _ in range(num_workers)]
    cleanup_task = asyncio.create_task(cleanup_temp_files())
    
    try:
        await bot.infinity_polling(timeout=30)
    except Exception as e:
        logger.error(f"Bot polling error: {e}")
    finally:
        for w in workers:
            w.cancel()
        cleanup_task.cancel()
        for task in processing_tasks:
            task.cancel()
        await asyncio.gather(*workers, cleanup_task, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())