import os  
import gc  
import logging  
import asyncio  
import aiofiles  
import requests  
import psutil  
import subprocess
from telebot.async_telebot import AsyncTeleBot  
from queue import Queue  

from config import API_TOKEN, TELEGRAM_FILE_LIMIT  
from handlers.youtube_handler import process_youtube, extract_audio  
from handlers.instagram_handler import process_instagram  
from handlers.facebook_handlers import process_facebook  
from handlers.common_handler import process_adult  
from handlers.x_handler import download_twitter_media  
from utils.logger import setup_logging  
from utils.streaming import *  
from utils.thumb_generator import *  

# Logging setup  
logger = setup_logging(logging.DEBUG)  

# Async Telegram bot  
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")  
download_queue = asyncio.Queue()  

# Supported platforms  
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
    """Detects platform of the URL and returns the handler function."""  
    for platform, (domains, handler) in SUPPORTED_PLATFORMS.items():  
        if any(domain in url for domain in domains):  
            return platform, handler  
    return None, None  

# ✅ Log memory usage  
def log_memory_usage():  
    memory = psutil.virtual_memory()  
    logger.info(f"Memory Usage: {memory.percent}% - Free: {memory.available / (1024 * 1024):.2f} MB")  

# ✅ Upload to MediaFire  
async def upload_to_mediafire(file_path):  
    try:  
        cmd = f"rclone copy '{file_path}' mediafire:YOUR_MEDIAFIRE_FOLDER --progress"  
        subprocess.run(cmd, shell=True, check=True)  
        return f"https://www.mediafire.com/file/{os.path.basename(file_path)}"  
    except Exception as e:  
        logger.error(f"MediaFire upload failed: {e}")  
        return None  

# ✅ Background Download Handler  
async def background_download(message, url):  
    """Handles the download process and sends the video to Telegram."""  
    try:  
        await bot.send_message(message.chat.id, "📥 **Download started...**")  
        logger.info(f"Processing URL: {url}")  

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

        # ✅ Convert M3U8 to MP4  
        if file_path and file_path.endswith(".m3u8"):  
            try:  
                converted_path = file_path.replace(".m3u8", ".mp4")  
                converted_path = await convert_m3u8_to_mp4(file_path, converted_path)  
                if converted_path:  
                    file_path = converted_path  
                    file_size = os.path.getsize(file_path)  
            except Exception as e:  
                logger.error(f"Error converting M3U8 to MP4: {e}")  
                await bot.send_message(message.chat.id, "❌ **Failed to convert video format.**")  
                return  

        # ✅ Upload large files to MediaFire  
        if not file_path or file_size > TELEGRAM_FILE_LIMIT:  
            if download_url:  
                await bot.send_message(message.chat.id, f"⚠️ **Video is too large.**\n📥 [Download here]({download_url})", disable_web_page_preview=True)  

                if handler == process_adult:  
                    clip_path = await download_best_clip(download_url, file_size)  
                    if clip_path:  
                        async with aiofiles.open(clip_path, "rb") as clip:  
                            await bot.send_video(message.chat.id, clip, caption="🎞 **Best 1-Min Scene Clip!**")  
                        os.remove(clip_path)  
            else:  
                mediafire_link = await upload_to_mediafire(file_path)  
                if mediafire_link:  
                    await bot.send_message(message.chat.id, f"📤 **Uploaded to MediaFire:** [Download here]({mediafire_link})", disable_web_page_preview=True)  
            return  

        log_memory_usage()  

        # ✅ Send thumbnail  
        thumbnail_path = await generate_thumbnail(file_path) if file_path else None  
        if handler == process_adult and thumbnail_path:  
            async with aiofiles.open(thumbnail_path, "rb") as thumb:  
                await bot.send_photo(message.chat.id, thumb, caption="✅ **Thumbnail received!**")  

        # ✅ Send video  
        async with aiofiles.open(file_path, "rb") as video:  
            await bot.send_video(message.chat.id, video, supports_streaming=True, timeout=600)  

        # ✅ Cleanup  
        for path in [file_path, thumbnail_path]:  
            if path and os.path.exists(path):  
                os.remove(path)  

        log_memory_usage()  
        gc.collect()  

    except Exception as e:  
        logger.error(f"Error: {e}")  
        await bot.send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")  

# ✅ Parallel Download Workers  
async def worker():  
    while True:  
        message, url = await download_queue.get()  
        await background_download(message, url)  
        download_queue.task_done()  

# ✅ Command Handlers  
@bot.message_handler(commands=["start"])  
async def start(message):  
    await bot.reply_to(message, "👋 **Welcome!**\nSend me a video link to download.")  

@bot.message_handler(commands=["audio"])  
async def download_audio(message):  
    url = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else None  
    if not url:  
        await bot.send_message(message.chat.id, "❌ **Please provide a valid YouTube URL.**")  
        return  

    await bot.send_message(message.chat.id, "🎵 **Extracting audio...**")  
    audio_file, file_size = await extract_audio_ffmpeg(url)  
    if audio_file:  
        async with aiofiles.open(audio_file, "rb") as audio:  
            await bot.send_audio(message.chat.id, audio, caption="🎧 **Here's your MP3!**")  
        os.remove(audio_file)  

# ✅ Run Bot  
async def main():  
    worker_tasks = [asyncio.create_task(worker()) for _ in range(3)]  
    await asyncio.gather(bot.infinity_polling(), *worker_tasks)  

if __name__ == "__main__":  
    asyncio.run(main())