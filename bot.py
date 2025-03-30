import os
import gc
import logging
import asyncio
import aiofiles
import re
import dropbox
import aiohttp
from dropbox.exceptions import AuthError, ApiError
from telebot.async_telebot import AsyncTeleBot
from yt_dlp import YoutubeDL

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

# Regex patterns for platforms
PLATFORM_PATTERNS = {
    "YouTube": re.compile(r"(youtube\\.com|youtu\\.be)"),
    "Instagram": re.compile(r"instagram\\.com"),
    "Facebook": re.compile(r"facebook\\.com"),
    "Twitter/X": re.compile(r"(x\\.com|twitter\\.com)"),
    "Adult": re.compile(r"(pornhub\\.com|xvideos\\.com|redtube\\.com|xhamster\\.com|xnxx\\.com)"),
}

# Platform handlers
PLATFORM_HANDLERS = {
    "YouTube": process_youtube,
    "Instagram": process_instagram,
    "Facebook": process_facebook,
    "Twitter/X": download_twitter_media,
    "Adult": process_adult,
}

def detect_platform(url):
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None

async def download_file(url, filename):
    """Downloads a file asynchronously."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                async with aiofiles.open(filename, "wb") as f:
                    await f.write(await response.read())

async def upload_to_dropbox(file_path, filename):
    """Uploads a file to Dropbox asynchronously."""
    try:
        dropbox_path = f"/telegram_uploads/{filename}"
        async with aiofiles.open(file_path, "rb") as f:
            file_size = os.path.getsize(file_path)
            chunk_size = 4 * 1024 * 1024  # 4MB
            
            if file_size > 140 * 1024 * 1024:
                session_start = await asyncio.to_thread(dbx.files_upload_session_start, await f.read(chunk_size))
                cursor = dropbox.files.UploadSessionCursor(session_id=session_start.session_id, offset=chunk_size)

                while f.tell() < file_size:
                    chunk = await f.read(chunk_size)
                    await asyncio.to_thread(dbx.files_upload_session_append_v2, chunk, cursor)
                    cursor.offset = f.tell()
                
                commit_info = dropbox.files.CommitInfo(path=dropbox_path)
                await asyncio.to_thread(dbx.files_upload_session_finish, await f.read(chunk_size), cursor, commit_info)
            else:
                await asyncio.to_thread(dbx.files_upload, await f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)

        shared_link = dbx.sharing_create_shared_link_with_settings(dropbox_path)
        return shared_link.url.replace("dl=0", "dl=1")
    except Exception as e:
        logger.error(f"Dropbox upload error: {e}")
        return None

async def process_download(message, url, is_audio=False):
    try:
        await bot.send_message(message.chat.id, "📥 Processing your request...")
        logger.info(f"Processing URL: {url}")

        platform = detect_platform(url)
        if not platform:
            await bot.send_message(message.chat.id, "⚠️ Unsupported URL.")
            return
        
        result = await (extract_audio_ffmpeg(url) if is_audio else PLATFORM_HANDLERS[platform](url))
        
        file_path, file_size, download_url = result if isinstance(result, tuple) else (result, None, None)

        if not file_path or (file_size and file_size > TELEGRAM_FILE_LIMIT):
            if file_path and os.path.exists(file_path):
                filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                dropbox_link = await upload_to_dropbox(file_path, filename)
                if dropbox_link:
                    await bot.send_message(message.chat.id, f"⚠️ File too large. [Download]({dropbox_link})")
                elif download_url:
                    await bot.send_message(message.chat.id, f"📥 [Download here]({download_url})")
                else:
                    await bot.send_message(message.chat.id, "❌ Download failed.")
            os.remove(file_path) if file_path and os.path.exists(file_path) else None
            gc.collect()
            return
        
        async with aiofiles.open(file_path, "rb") as file:
            await bot.send_audio(message.chat.id, file) if is_audio else await bot.send_video(message.chat.id, file)
        os.remove(file_path)
        gc.collect()
    except Exception as e:
        logger.error(f"Error in process_download: {e}")
        await bot.send_message(message.chat.id, f"❌ Error: {e}")

async def worker():
    while True:
        message, url, is_audio = await download_queue.get()
        await process_download(message, url, is_audio)
        download_queue.task_done()

@bot.message_handler(commands=["start", "help"])
async def send_welcome(message):
    await bot.send_message(message.chat.id, "🤖 Send a URL to download media.")

@bot.message_handler(commands=["audio"])
async def handle_audio_request(message):
    url = message.text.replace("/audio", "").strip()
    if url:
        await download_queue.put((message, url, True))
        await bot.send_message(message.chat.id, "✅ Added to audio queue!")

@bot.message_handler(func=lambda msg: True, content_types=["text"])
async def handle_message(message):
    url = message.text.strip()
    await download_queue.put((message, url, False))
    await bot.send_message(message.chat.id, "✅ Added to download queue!")

async def main():
    for _ in range(5):
        asyncio.create_task(worker())
    await bot.infinity_polling()

if __name__ == "__main__":
    asyncio.run(main())
