import os
import gc
import logging
import asyncio
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

# ---------------- CONSTANTS ----------------
MAX_MEMORY_USAGE = 500 * 1024 * 1024  # 500MB
MAX_CONCURRENT_DOWNLOADS = 2
CLEANUP_INTERVAL = 300  # 5 minutes

# ---------------- LOGGER ----------------
logger = setup_logging(logging.DEBUG)

# ---------------- BOT ----------------
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()
download_semaphore = Semaphore(MAX_CONCURRENT_DOWNLOADS)

mega = None
active_downloads = set()

# ---------------- PLATFORMS ----------------
PLATFORM_PATTERNS = {
    "YouTube": re.compile(r"(youtube\.com|youtu\.be)"),
    "Instagram": re.compile(r"instagram\.com"),
    "Facebook": re.compile(r"facebook\.com"),
    "Twitter/X": re.compile(r"(x\.com|twitter\.com)"),
    "Adult": re.compile(r"(pornhub|xvideos|xnxx|xhamster)"),
}

PLATFORM_HANDLERS = {
    "YouTube": process_youtube,
    "Instagram": process_instagram,
    "Facebook": process_facebook,
    "Twitter/X": download_twitter_media,
    "Adult": process_adult,
}

# ---------------- HELPERS ----------------
def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def detect_platform(url):
    for name, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return name
    return None

async def check_memory():
    return psutil.Process(os.getpid()).memory_info().rss < MAX_MEMORY_USAGE

async def send_message(chat_id, text):
    await bot.send_message(chat_id, text)

# ---------------- MEGA ----------------
async def get_mega_client():
    global mega
    if mega is None:
        m = Mega()
        mega = await asyncio.to_thread(m.login, MEGA_EMAIL, MEGA_PASSWORD)
        logger.info("✅ MEGA logged in")
    return mega

async def upload_to_mega(file_path):
    try:
        client = await get_mega_client()
        f = await asyncio.to_thread(client.upload, file_path)
        return await asyncio.to_thread(client.get_upload_link, f)
    except Exception as e:
        logger.error(f"MEGA upload error: {e}")
        return None

# ---------------- CLEANUP ----------------
async def cleanup_files():
    while True:
        try:
            for f in os.listdir(DOWNLOAD_DIR):
                p = os.path.join(DOWNLOAD_DIR, f)
                if os.path.isfile(p) and time.time() - os.path.getctime(p) > 3600:
                    os.remove(p)
            gc.collect()
            await asyncio.sleep(CLEANUP_INTERVAL)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            await asyncio.sleep(60)

# ---------------- DOWNLOAD ----------------
async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start=None, end=None):
    if not await check_memory():
        await send_message(message.chat.id, "⚠️ Server busy, try later")
        return

    async with download_semaphore:
        await send_message(message.chat.id, "📥 Processing...")

        platform = detect_platform(url)
        if not platform:
            await send_message(message.chat.id, "❌ Unsupported URL")
            return

        try:
            if is_video_trim:
                result = await process_video_trim(url, start, end)
            elif is_audio_trim:
                result = await process_audio_trim(url, start, end)
            elif is_audio:
                result = await extract_audio_ffmpeg(url)
            else:
                result = await PLATFORM_HANDLERS[platform](url)

            if not result:
                await send_message(message.chat.id, "❌ Download failed")
                return

            paths = result[0] if isinstance(result[0], list) else [result[0]]
            size = result[1] if len(result) > 1 else None

            for file_path in paths:
                if not os.path.exists(file_path):
                    continue

                file_size = size or os.path.getsize(file_path)

                if file_size > TELEGRAM_FILE_LIMIT:
                    link = await upload_to_mega(file_path)
                    await send_message(message.chat.id, f"📦 File too large:\n{link}")
                else:
                    with open(file_path, "rb") as f:
                        if is_audio or is_audio_trim:
                            await bot.send_audio(message.chat.id, f)
                        else:
                            await bot.send_video(
                                message.chat.id,
                                f,
                                supports_streaming=True
                            )

                os.remove(file_path)

        except Exception as e:
            logger.error(f"Download error: {e}")
            await send_message(message.chat.id, f"❌ Error: {e}")

        gc.collect()

# ---------------- IMAGE ----------------
async def process_image_download(message, url):
    await send_message(message.chat.id, "🖼 Processing image...")
    result = await process_instagram_image(url)
    paths = result if isinstance(result, list) else [result]

    for p in paths:
        if not os.path.exists(p):
            continue

        if os.path.getsize(p) > TELEGRAM_FILE_LIMIT:
            link = await upload_to_mega(p)
            await send_message(message.chat.id, link)
        else:
            with open(p, "rb") as f:
                await bot.send_photo(message.chat.id, f)

        os.remove(p)

# ---------------- WORKER ----------------
async def worker():
    while True:
        task = await download_queue.get()
        if len(task) == 2:
            await process_image_download(*task)
        else:
            await process_download(*task)
        download_queue.task_done()

# ---------------- COMMANDS ----------------
@bot.message_handler(commands=["start", "help"])
async def start_cmd(message):
    await send_message(message.chat.id, "🤖 Media Downloader\nSend a URL")

@bot.message_handler(commands=["audio"])
async def audio_cmd(message):
    url = message.text.replace("/audio", "").strip()
    await download_queue.put((message, url, True, False, False, None, None))

@bot.message_handler(commands=["image"])
async def image_cmd(message):
    url = message.text.replace("/image", "").strip()
    await download_queue.put((message, url))

@bot.message_handler(func=lambda m: True)
async def handle_url(message):
    await download_queue.put((message, message.text.strip(), False, False, False, None, None))
    await send_message(message.chat.id, "⏳ Added to queue")

# ---------------- MAIN ----------------
async def main():
    # 🔥 FORCE INITIAL COOKIE GENERATION
    await auto_refresh_cookies()

    # 🔁 KEEP REFRESHING IN BACKGROUND
    asyncio.create_task(auto_refresh_cookies())
    asyncio.create_task(cleanup_files())

    for _ in range(3):
        asyncio.create_task(worker())

    await bot.infinity_polling(timeout=30)

if __name__ == "__main__":
    asyncio.run(main())