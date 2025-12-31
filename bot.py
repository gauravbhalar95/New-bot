import os
import gc
import re
import time
import asyncio
import logging
import psutil
from datetime import datetime, timezone
from asyncio import Semaphore

from telebot.async_telebot import AsyncTeleBot
from mega import Mega

from config import (
    API_TOKEN,
    DOWNLOAD_DIR,
    TELEGRAM_FILE_LIMIT,
    MEGA_EMAIL,
    MEGA_PASSWORD,
)

from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.image_handlers import process_instagram_image
from handlers.facebook_handlers import process_facebook
from handlers.x_handler import download_twitter_media
from handlers.common_handler import process_adult
from handlers.trim_handlers import process_video_trim, process_audio_trim

from utils.logger import setup_logging
from utils.instagram_cookies import auto_refresh_cookies

# ================= CONFIG =================
MAX_MEMORY_USAGE = 450 * 1024 * 1024  # 450MB (safe for Koyeb)
MAX_CONCURRENT_DOWNLOADS = 1
CLEANUP_INTERVAL = 300

# ================= LOGGING =================
logger = setup_logging(logging.INFO)

# ================= BOT =================
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()
download_semaphore = Semaphore(MAX_CONCURRENT_DOWNLOADS)

# ================= MEGA =================
mega_client = None

# ================= PLATFORM DETECTION =================
PLATFORM_PATTERNS = {
    "YouTube": re.compile(r"(youtube\.com|youtu\.be)"),
    "Instagram": re.compile(r"instagram\.com"),
    "Facebook": re.compile(r"facebook\.com"),
    "Twitter": re.compile(r"(x\.com|twitter\.com)"),
    "Adult": re.compile(r"(pornhub|xvideos|xnxx|xhamster)"),
}

PLATFORM_HANDLERS = {
    "YouTube": process_youtube,
    "Instagram": process_instagram,
    "Facebook": process_facebook,
    "Twitter": download_twitter_media,
    "Adult": process_adult,
}

# ================= UTILS =================
def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def detect_platform(url):
    for name, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return name
    return None

async def memory_ok():
    return psutil.Process(os.getpid()).memory_info().rss < MAX_MEMORY_USAGE

# ================= CLEANUP =================
async def cleanup_task():
    while True:
        try:
            for f in os.listdir(DOWNLOAD_DIR):
                path = os.path.join(DOWNLOAD_DIR, f)
                if os.path.isfile(path) and time.time() - os.path.getctime(path) > 3600:
                    os.remove(path)
            gc.collect()
        except Exception as e:
            logger.error(f"[{now()}] Cleanup error: {e}")
        await asyncio.sleep(CLEANUP_INTERVAL)

# ================= MEGA =================
async def get_mega():
    global mega_client
    if mega_client is None:
        try:
            m = Mega()
            mega_client = await asyncio.to_thread(m.login, MEGA_EMAIL, MEGA_PASSWORD)
            logger.info("MEGA logged in")
        except Exception as e:
            logger.error(f"MEGA login failed: {e}")
            return None
    return mega_client

async def upload_to_mega(path):
    try:
        mega = await get_mega()
        file = await asyncio.to_thread(mega.upload, path)
        return await asyncio.to_thread(mega.get_upload_link, file)
    except Exception as e:
        logger.error(f"MEGA upload error: {e}")
        return None

# ================= CORE DOWNLOAD =================
async def process_download(task):
    message = task["message"]
    url = task["url"]

    async with download_semaphore:
        if not await memory_ok():
            await bot.send_message(message.chat.id, "⚠️ Server busy. Try again later.")
            return

        platform = detect_platform(url)
        if not platform:
            await bot.send_message(message.chat.id, "❌ Unsupported URL")
            return

        await bot.send_message(message.chat.id, "📥 Processing...")

        try:
            # ---------- PROCESS ----------
            if task["type"] == "audio":
                file_path, size = await extract_audio_ffmpeg(url)

            elif task["type"] == "video_trim":
                file_path, size = await process_video_trim(
                    url, task["start"], task["end"]
                )

            elif task["type"] == "audio_trim":
                file_path, size = await process_audio_trim(
                    url, task["start"], task["end"]
                )

            else:
                result = await PLATFORM_HANDLERS[platform](url)
                if isinstance(result, tuple):
                    file_path, size = result
                else:
                    file_path = result
                    size = os.path.getsize(file_path)

            # ---------- SEND ----------
            if size > TELEGRAM_FILE_LIMIT:
                link = await upload_to_mega(file_path)
                await bot.send_message(message.chat.id, f"📦 File too large:\n{link}")
            else:
                if task["type"] in ["audio", "audio_trim"]:
                    await bot.send_audio(message.chat.id, open(file_path, "rb"))
                else:
                    await bot.send_video(
                        message.chat.id,
                        open(file_path, "rb"),
                        supports_streaming=True,
                    )

        except Exception as e:
            logger.error(f"Download error: {e}")
            await bot.send_message(message.chat.id, f"❌ Error: {e}")

        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            gc.collect()

# ================= IMAGE =================
async def process_image(message, url):
    await bot.send_message(message.chat.id, "🖼️ Processing image...")
    files = await process_instagram_image(url)

    for img in files:
        if os.path.getsize(img) > TELEGRAM_FILE_LIMIT:
            link = await upload_to_mega(img)
            await bot.send_message(message.chat.id, link)
        else:
            await bot.send_photo(message.chat.id, open(img, "rb"))
        os.remove(img)

# ================= WORKER =================
async def worker():
    while True:
        task = await download_queue.get()
        logger.info(f"Worker got task: {task}")
        try:
            if task["type"] == "image":
                await process_image(task["message"], task["url"])
            else:
                await process_download(task)
        finally:
            download_queue.task_done()

# ================= COMMANDS =================
@bot.message_handler(commands=["start", "help"])
async def start(message):
    await bot.send_message(
        message.chat.id,
        "🤖 Media Bot\n\n/audio <url>\n/image <url>\n/trim <url> 00:00:10 00:00:20",
    )

@bot.message_handler(commands=["audio"])
async def audio_cmd(message):
    url = message.text.replace("/audio", "").strip()
    await download_queue.put(
        {"type": "audio", "url": url, "message": message}
    )
    await bot.send_message(message.chat.id, "🎵 Added to queue")

@bot.message_handler(commands=["image"])
async def image_cmd(message):
    url = message.text.replace("/image", "").strip()
    await download_queue.put(
        {"type": "image", "url": url, "message": message}
    )
    await bot.send_message(message.chat.id, "🖼️ Added to queue")

@bot.message_handler(commands=["trim"])
async def trim_cmd(message):
    m = re.search(r"(https?://\S+)\s+(\d+:\d+:\d+)\s+(\d+:\d+:\d+)", message.text)
    if m:
        await download_queue.put({
            "type": "video_trim",
            "url": m.group(1),
            "start": m.group(2),
            "end": m.group(3),
            "message": message,
        })

@bot.message_handler(func=lambda m: True)
async def normal_url(message):
    await download_queue.put(
        {"type": "video", "url": message.text.strip(), "message": message}
    )
    await bot.send_message(message.chat.id, "🎬 Added to queue")

# ================= MAIN =================
async def main():
    asyncio.create_task(cleanup_task())
    asyncio.create_task(auto_refresh_cookies())

    for _ in range(1):
        asyncio.create_task(worker())

    await bot.infinity_polling(timeout=30)

if __name__ == "__main__":
    asyncio.run(main())