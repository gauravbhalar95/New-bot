import os
import gc
import logging
import asyncio
import aiofiles
import requests
import telebot
import psutil
import nest_asyncio
from flask import Flask, request
from mega import Mega
from telebot.async_telebot import AsyncTeleBot

from config import API_TOKEN, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from utils.logger import setup_logging
from utils.streaming import *
from utils.thumb_generator import *

# Logging setup
logger = setup_logging(logging.DEBUG)

nest_asyncio.apply()

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()

# Flask app for webhook
app = Flask(__name__)

# MEGA client
mega = Mega()
mega_client = None  # Store MEGA login session
user_credentials = {}  # Store credentials for relogin if needed

# Supported platforms and handlers
SUPPORTED_PLATFORMS = {
    "YouTube": (["youtube.com", "youtu.be"], process_youtube),
    "Instagram": (["instagram.com"], process_instagram),
    "Facebook": (["facebook.com"], process_facebook),
    "Twitter/X": (["x.com", "twitter.com"], download_twitter_media),
    "Adult": (
        ["pornhub.com", "xvideos.com", "redtube.com", "xhamster.com", "xnxx.com"],
        process_adult,
    ),
}

def detect_platform(url):
    for platform, (domains, handler) in SUPPORTED_PLATFORMS.items():
        if any(domain in url for domain in domains):
            return platform, handler
    return None, None

# Command: /meganz <username> <password>
@bot.message_handler(commands=["meganz"])
async def login_mega(message):
    global mega_client
    try:
        args = message.text.split()
        if len(args) == 3:
            username, password = args[1], args[2]
            mega_client = mega.login(username, password)
            user_credentials['username'] = username
            user_credentials['password'] = password
            await bot.send_message(message.chat.id, "✅ **Logged into MEGA successfully!**")
        else:
            # Anonymous login (limited access)
            mega_client = mega.login()
            await bot.send_message(message.chat.id, "✅ **Logged into MEGA anonymously (limited access).**")
    except Exception as e:
        await bot.send_message(message.chat.id, f"❌ **MEGA login failed:** {e}")

# Upload files to MEGA
async def upload_to_mega(file_path, chat_id):
    global mega_client
    if not mega_client:
        await bot.send_message(chat_id, "❌ **Please log in first using `/meganz <username> <password>`.**")
        return

    try:
        await bot.send_message(chat_id, "📤 **Uploading to MEGA...**")

        # Upload file
        uploaded_file = mega_client.upload(file_path)
        public_url = mega_client.get_upload_link(uploaded_file)

        await bot.send_message(chat_id, f"✅ **Uploaded to MEGA:** [Download here]({public_url})")
    except Exception as e:
        await bot.send_message(chat_id, f"❌ **Failed to upload to MEGA:** {e}")
    finally:
        # Clean up local file
        if os.path.exists(file_path):
            os.remove(file_path)

# Download logic
async def background_download(message, url):
    try:
        await bot.send_message(message.chat.id, "📥 **Download started...**")
        platform, handler = detect_platform(url)
        if not handler:
            await bot.send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        task = asyncio.create_task(handler(url))
        result = await task

        if isinstance(result, tuple):
            if len(result) == 3:
                file_path, file_size, download_url = result
            elif len(result) == 2:
                file_path, file_size = result
                download_url = None
            else:
                await bot.send_message(message.chat.id, "❌ **Error processing video.**")
                return

        if file_path and file_size > TELEGRAM_FILE_LIMIT:
            if download_url:
                await bot.send_message(
                    message.chat.id,
                    f"⚠️ **The video is too large for Telegram.**\n📥 [Download here]({download_url})",
                    disable_web_page_preview=True
                )
            elif mega_client:
                await upload_to_mega(file_path, message.chat.id)
            else:
                await bot.send_message(message.chat.id, "❌ **Download failed.**")
            return

        async with aiofiles.open(file_path, "rb") as video:
            await bot.send_video(message.chat.id, video, supports_streaming=True)

        if file_path and os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        logger.error(f"Error: {e}")
        await bot.send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

# Worker for processing download queue
async def worker():
    while True:
        message, url = await download_queue.get()
        await background_download(message, url)
        download_queue.task_done()

# Start command
@bot.message_handler(commands=["start"])
async def start(message):
    user_name = message.from_user.first_name or "User"
    await bot.reply_to(message, f"👋 **Welcome {user_name}!**\n\nSend me a video link to download.")

# Download audio
@bot.message_handler(commands=["audio"])
async def download_audio(message):
    url = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else None
    if not url:
        await bot.send_message(message.chat.id, "❌ **Please provide a valid YouTube URL.**")
        return

    await bot.send_message(message.chat.id, "🎵 **Extracting audio... Please wait.**")
    audio_file, _ = await extract_audio_ffmpeg(url)

    if audio_file:
        async with aiofiles.open(audio_file, "rb") as audio:
            await bot.send_audio(message.chat.id, audio, caption="🎧 **Here's your MP3 file!**")
        os.remove(audio_file)
    else:
        await bot.send_message(message.chat.id, "❌ **Failed to extract audio.**")

# Main loop
async def main():
    logger.info("Bot is starting...")
    worker_tasks = [asyncio.create_task(worker()) for _ in range(3)]
    await asyncio.gather(bot.infinity_polling(), *worker_tasks)

if __name__ == "__main__":
    asyncio.run(main())