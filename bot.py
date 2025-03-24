import os      
import gc      
import logging      
import asyncio      
import aiofiles      
import re      
import telebot      
import psutil      
from telebot.async_telebot import AsyncTeleBot      

from config import API_TOKEN, TELEGRAM_FILE_LIMIT      
from handlers.youtube_handler import process_youtube, extract_audio      
from handlers.instagram_handler import process_instagram      
from handlers.facebook_handlers import process_facebook      
from handlers.common_handler import process_adult      
from handlers.x_handler import download_twitter_media      
from utils.logger import setup_logging      
from utils.streaming import *      
from utils.thumb_generator import *      
from handlers.trim_handlers import process_youtube_request      

# Logging setup      
logger = setup_logging(logging.DEBUG)      

# Async Telegram bot setup      
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")      
download_queue = asyncio.Queue()      

# Supported platforms and handlers      
SUPPORTED_PLATFORMS = {      
    "YouTube": (["youtube.com", "youtu.be"], process_youtube),      
    "Instagram": (["instagram.com"], process_instagram),      
    "Facebook": (["facebook.com"], process_facebook),      
    "Twitter/X": (["x.com", "twitter.com"], download_twitter_media),      
    "Adult": (["pornhub.com", "xvideos.com", "redtube.com", "xhamster.com", "xnxx.com"], process_adult),      
}      

def detect_platform(url):      
    """Detects the platform of the given URL and returns the corresponding handler function."""      
    for platform, (domains, handler) in SUPPORTED_PLATFORMS.items():      
        if any(domain in url for domain in domains):      
            return platform, handler      
    return None, None      

# Background download function      
async def background_download(message, url):      
    """Handles the entire download process and sends the video to Telegram."""      
    try:      
        await bot.send_message(message.chat.id, "📥 **Download started...**")      
        logger.info(f"Processing URL: {url}")      

        platform, handler = detect_platform(url)      
        if not handler:      
            await bot.send_message(message.chat.id, "⚠️ **Unsupported URL.**")      
            return      

        # Extract start & end time from URL format: "url start end"
        time_match = re.search(r"(\S+)\s+(\d+)\s+(\d+)", url)      
        start_time, end_time = None, None      

        if time_match:      
            url, start_time, end_time = time_match.groups()      
            start_time, end_time = int(start_time), int(end_time)      

        # YouTube-specific handling      
        if platform == "YouTube":      
            if start_time is not None and end_time is not None:      
                logger.info(f"Trimming YouTube video: Start={start_time}s, End={end_time}s")      
                result = await process_youtube_request(text)    
            else:      
                result = await process_youtube(url)      
        else:      
            result = await handler(url)      

        if isinstance(result, tuple):      
            file_path, file_size, download_url = result if len(result) == 3 else (*result, None)      

        # If file is too large, provide a direct download link instead      
        if not file_path or file_size > TELEGRAM_FILE_LIMIT:      
            if download_url:      
                await bot.send_message(      
                    message.chat.id,      
                    f"⚠️ **The video is too large for Telegram.**\n📥 [Download here]({download_url})",      
                    disable_web_page_preview=True      
                )      
            else:      
                await bot.send_message(message.chat.id, "❌ **Download failed.**")      
            return      

        # Send video file with increased timeout      
        async with aiofiles.open(file_path, "rb") as video:      
            await bot.send_video(message.chat.id, video, supports_streaming=True, timeout=600)      

        # Cleanup      
        if file_path and os.path.exists(file_path):      
            os.remove(file_path)      

        gc.collect()      

    except Exception as e:      
        logger.error(f"Error: {e}")      
        await bot.send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")      

# Worker function for parallel downloads      
async def worker():      
    while True:      
        message, url = await download_queue.get()      
        await background_download(message, url)      
        download_queue.task_done()      

# Handle incoming URLs      
@bot.message_handler(func=lambda message: True, content_types=["text"])      
async def handle_message(message):      
    url = message.text.strip()      
    await download_queue.put((message, url))      
    await bot.send_message(message.chat.id, "✅ **Added to download queue!**")      

# Run bot      
async def main():      
    asyncio.create_task(worker())  # Worker runs in the background      
    await bot.polling()  # Start bot polling      

if __name__ == "__main__":      
    asyncio.run(main())