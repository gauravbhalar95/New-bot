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

from config import (
    API_TOKEN,
    DOWNLOAD_DIR,
    TELEGRAM_FILE_LIMIT,
    MEGA_EMAIL,
    MEGA_PASSWORD,
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

# ---------------- CONFIG ---------------- #

MAX_MEMORY_USAGE = 500 * 1024 * 1024
MAX_CONCURRENT_DOWNLOADS = 2
CLEANUP_INTERVAL = 300

logger = setup_logging(logging.INFO)

bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()
download_semaphore = Semaphore(MAX_CONCURRENT_DOWNLOADS)

mega_client = None
active_downloads = set()

PLATFORM_PATTERNS = {
    "YouTube": re.compile(r"(youtube\.com|youtu\.be)"),
    "Instagram": re.compile(r"instagram\.com"),
    "Facebook": re.compile(r"facebook\.com"),
    "Twitter/X": re.compile(r"(x\.com|twitter\.com)"),
    "Adult": re.compile(r"(pornhub\.com|xvideos\.com|xnxx\.com|xhamster\.com)"),
}

PLATFORM_HANDLERS = {
    "YouTube": process_youtube,
    "Instagram": process_instagram,
    "Facebook": process_facebook,
    "Twitter/X": download_twitter_media,
    "Adult": process_adult,
}

# ---------------- HELPERS ---------------- #

def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def detect_platform(url: str):
    for name, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return name
    return None

async def memory_ok():
    return psutil.Process(os.getpid()).memory_info().rss < MAX_MEMORY_USAGE

async def cleanup_task():
    while True:
        try:
            if os.path.exists(DOWNLOAD_DIR):
                for f in os.listdir(DOWNLOAD_DIR):
                    path = os.path.join(DOWNLOAD_DIR, f)
                    if os.path.isfile(path) and time.time() - os.path.getctime(path) > 3600:
                        os.remove(path)
            gc.collect()
        except Exception as e:
            logger.error(f"[{utc_now()}] Cleanup error: {e}")
        await asyncio.sleep(CLEANUP_INTERVAL)

async def send_text(chat_id, text):
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"Send message error: {e}")

# ---------------- MEGA ---------------- #

async def get_mega():
    global mega_client
    if mega_client is None:
        m = Mega()
        mega_client = await asyncio.to_thread(m.login, MEGA_EMAIL, MEGA_PASSWORD)
    return mega_client

async def upload_mega(file_path):
    try:
        m = await get_mega()
        f = await asyncio.to_thread(m.upload, file_path)
        return await asyncio.to_thread(m.get_upload_link, f)
    except Exception as e:
        logger.error(f"MEGA upload failed: {e}")
        return None

# ---------------- DOWNLOAD ---------------- #

async def process_download(message, url, audio=False, vtrim=False, atrim=False, start=None, end=None):
    if not await memory_ok():
        return await send_text(message.chat.id, "⚠️ Server busy. Try later.")

    async with download_semaphore:
        platform = detect_platform(url)
        if not platform:
            return await send_text(message.chat.id, "❌ Unsupported URL")

        await send_text(message.chat.id, "📥 Processing...")

        try:
            if vtrim:
                file_path, _ = await process_video_trim(url, start, end)
                paths = [file_path]
            elif atrim:
                file_path, _ = await process_audio_trim(url, start, end)
                paths = [file_path]
            elif audio:
                file_path, _ = await extract_audio_ffmpeg(url)
                paths = [file_path]
            else:
                result = await PLATFORM_HANDLERS[platform](url)
                paths = result[0] if isinstance(result, tuple) else [result]

            for path in paths:
                if not path or not os.path.exists(path):
                    continue

                size = os.path.getsize(path)

                if size > TELEGRAM_FILE_LIMIT:
                    link = await upload_mega(path)
                    await send_text(message.chat.id, f"📦 Large file:\n{link}")
                else:
                    async with aiofiles.open(path, "rb") as f:
                        data = await f.read()
                        if audio or atrim:
                            await bot.send_audio(message.chat.id, data)
                        else:
                            await bot.send_video(message.chat.id, data, supports_streaming=True)

                os.remove(path)

        except Exception as e:
            logger.exception(e)
            await send_text(message.chat.id, f"❌ Error: {e}")

# ---------------- IMAGE ---------------- #

async def process_image(message, url):
    await send_text(message.chat.id, "🖼️ Processing image...")
    try:
        result = await process_instagram_image(url)
        files = result if isinstance(result, list) else [result]

        for path in files:
            if not path or not os.path.exists(path):
                continue

            size = os.path.getsize(path)
            if size > TELEGRAM_FILE_LIMIT:
                link = await upload_mega(path)
                await send_text(message.chat.id, link)
            else:
                async with aiofiles.open(path, "rb") as f:
                    await bot.send_photo(message.chat.id, await f.read())
            os.remove(path)

    except Exception as e:
        logger.error(e)
        await send_text(message.chat.id, "❌ Image failed")

# ---------------- WORKER ---------------- #

async def worker():
    while True:
        task = await download_queue.get()
        try:
            if len(task) == 2:
                await process_image(*task)
            else:
                await process_download(*task)
        finally:
            download_queue.task_done()

# ---------------- COMMANDS ---------------- #

@bot.message_handler(commands=["start", "help"])
async def start(m):
    await send_text(m.chat.id, "🤖 Media Downloader\nSend link")

@bot.message_handler(commands=["audio"])
async def audio_cmd(m):
    url = m.text.replace("/audio", "").strip()
    await download_queue.put((m, url, True, False, False, None, None))

@bot.message_handler(commands=["image"])
async def image_cmd(m):
    url = m.text.replace("/image", "").strip()
    await download_queue.put((m, url))

@bot.message_handler(func=lambda m: True, content_types=["text"])
async def normal(m):
    await download_queue.put((m, m.text.strip(), False, False, False, None, None))

# ---------------- MAIN ---------------- #

async def main():
    asyncio.create_task(auto_refresh_cookies())
    asyncio.create_task(cleanup_task())

    for _ in range(3):
        asyncio.create_task(worker())

    # ✅ FIXED POLLING (NO long_polling_timeout)
    await bot.infinity_polling(timeout=30)

if __name__ == "__main__":
    asyncio.run(main())