import os
import gc
import re
import time
import psutil
import asyncio
import logging
import aiofiles
from datetime import datetime, timezone
from asyncio import Semaphore

from mega import Mega
from telebot.async_telebot import AsyncTeleBot

from config import (
    API_TOKEN,
    DOWNLOAD_DIR,
    TELEGRAM_FILE_LIMIT,
    MEGA_EMAIL,
    MEGA_PASSWORD,
    ADMIN_IDS,
)

from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.x_handler import download_twitter_media
from handlers.common_handler import process_adult
from handlers.trim_handlers import process_video_trim, process_audio_trim
from handlers.image_handlers import process_instagram_image

from utils.logger import setup_logging
from utils.instagram_cookies import auto_refresh_cookies


# ================= CONFIG =================
MAX_MEMORY_USAGE = 500 * 1024 * 1024  # 500MB
MAX_CONCURRENT_DOWNLOADS = 2
CLEANUP_INTERVAL = 300  # 5 min

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logger = setup_logging(logging.INFO)
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")

download_queue = asyncio.Queue()
download_semaphore = Semaphore(MAX_CONCURRENT_DOWNLOADS)
active_downloads = set()

mega_client = None


# ================= UTILS =================
def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def detect_platform(url: str):
    patterns = {
        "YouTube": r"(youtube\.com|youtu\.be)",
        "Instagram": r"instagram\.com",
        "Facebook": r"facebook\.com",
        "Twitter": r"(x\.com|twitter\.com)",
        "Adult": r"(pornhub|xvideos|xnxx|xhamster|redtube)",
    }
    for k, v in patterns.items():
        if re.search(v, url):
            return k
    return None


async def memory_ok():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss < MAX_MEMORY_USAGE


async def send_msg(chat_id, text):
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"[{utc_now()}] send_message error: {e}")


# ================= MEGA =================
async def get_mega():
    global mega_client
    if mega_client:
        return mega_client
    try:
        m = Mega()
        mega_client = await asyncio.to_thread(m.login, MEGA_EMAIL, MEGA_PASSWORD)
        logger.info("MEGA logged in")
        return mega_client
    except Exception as e:
        logger.error(f"MEGA login failed: {e}")
        return None


async def upload_mega(file_path):
    try:
        client = await get_mega()
        if not client:
            return None
        file = await asyncio.to_thread(client.upload, file_path)
        link = await asyncio.to_thread(client.get_upload_link, file)
        return link
    except Exception as e:
        logger.error(f"MEGA upload error: {e}")
        return None


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
            logger.error(f"Cleanup error: {e}")
        await asyncio.sleep(CLEANUP_INTERVAL)


# ================= CORE DOWNLOAD =================
async def process_download(message, url, audio=False, vtrim=False, atrim=False, start=None, end=None):
    download_id = f"{message.chat.id}_{time.time()}"
    active_downloads.add(download_id)

    try:
        if not await memory_ok():
            await send_msg(message.chat.id, "⚠️ Server busy, try later")
            return

        async with download_semaphore:
            await send_msg(message.chat.id, "📥 Processing...")

            platform = detect_platform(url)
            if not platform:
                await send_msg(message.chat.id, "❌ Unsupported URL")
                return

            result = None
            if vtrim:
                result = await process_video_trim(url, start, end)
            elif atrim:
                result = await process_audio_trim(url, start, end)
            elif audio:
                result = await extract_audio_ffmpeg(url)
            else:
                handlers = {
                    "YouTube": process_youtube,
                    "Instagram": process_instagram,
                    "Facebook": process_facebook,
                    "Twitter": download_twitter_media,
                    "Adult": process_adult,
                }
                result = await handlers[platform](url)

            if not result:
                await send_msg(message.chat.id, "❌ Download failed")
                return

            files = []
            if isinstance(result, tuple):
                files = result[0] if isinstance(result[0], list) else [result[0]]
            elif isinstance(result, list):
                files = result
            else:
                files = [result]

            for file_path in files:
                if not file_path or not os.path.exists(file_path):
                    continue

                size = os.path.getsize(file_path)

                if size > TELEGRAM_FILE_LIMIT:
                    link = await upload_mega(file_path)
                    if link:
                        await send_msg(message.chat.id, f"📦 File too large:\n{link}")
                else:
                    async with aiofiles.open(file_path, "rb") as f:
                        data = await f.read()
                        if audio or atrim:
                            await bot.send_audio(message.chat.id, data)
                        else:
                            await bot.send_video(message.chat.id, data, supports_streaming=True)

                os.remove(file_path)

    except Exception as e:
        logger.error(f"process_download error: {e}")
        await send_msg(message.chat.id, f"❌ Error: {e}")
    finally:
        active_downloads.discard(download_id)
        gc.collect()


# ================= IMAGE =================
async def process_image(message, url):
    try:
        await send_msg(message.chat.id, "🖼️ Processing image...")
        result = await process_instagram_image(url)
        files = result if isinstance(result, list) else [result]

        for path in files:
            if not path or not os.path.exists(path):
                continue
            size = os.path.getsize(path)
            if size > TELEGRAM_FILE_LIMIT:
                link = await upload_mega(path)
                if link:
                    await send_msg(message.chat.id, link)
            else:
                async with aiofiles.open(path, "rb") as f:
                    await bot.send_photo(message.chat.id, await f.read())
            os.remove(path)

    except Exception as e:
        logger.error(f"image error: {e}")
        await send_msg(message.chat.id, f"❌ {e}")


# ================= WORKER =================
async def worker():
    while True:
        task = await download_queue.get()
        if len(task) == 2:
            await process_image(*task)
        else:
            await process_download(*task)
        download_queue.task_done()


# ================= BOT COMMANDS =================
@bot.message_handler(commands=["start", "help"])
async def start_cmd(message):
    await send_msg(message.chat.id, "🤖 Media Downloader Bot\nSend any URL")


@bot.message_handler(commands=["audio"])
async def audio_cmd(message):
    url = message.text.replace("/audio", "").strip()
    if url:
        await download_queue.put((message, url, True, False, False, None, None))


@bot.message_handler(commands=["image"])
async def image_cmd(message):
    url = message.text.replace("/image", "").strip()
    if url:
        await download_queue.put((message, url))


@bot.message_handler(commands=["trim"])
async def trim_cmd(message):
    m = re.search(r"(https?://\S+)\s+(\d+:\d+:\d+)\s+(\d+:\d+:\d+)", message.text)
    if m:
        await download_queue.put((message, m[1], False, True, False, m[2], m[3]))


@bot.message_handler(commands=["trimAudio"])
async def trim_audio_cmd(message):
    m = re.search(r"(https?://\S+)\s+(\d+:\d+:\d+)\s+(\d+:\d+:\d+)", message.text)
    if m:
        await download_queue.put((message, m[1], False, False, True, m[2], m[3]))


@bot.message_handler(func=lambda m: True, content_types=["text"])
async def all_text(message):
    await download_queue.put((message, message.text, False, False, False, None, None))


# ================= MAIN =================
async def main():
    asyncio.create_task(auto_refresh_cookies())
    asyncio.create_task(cleanup_task())

    for _ in range(min(3, os.cpu_count() or 1)):
        asyncio.create_task(worker())

    await bot.infinity_polling(timeout=30, long_polling_timeout=30)


if __name__ == "__main__":
    asyncio.run(main())