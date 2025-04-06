import os
import re
import asyncio
import traceback
import logging
import gc
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from utils.platform_detector import detect_platform
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram, process_instagram_image
from handlers.facebook_handler import process_facebook
from handlers.twitter_handler import process_twitter
from handlers.adult_handler import process_adult
from handlers.common_handler import extract_audio_ffmpeg, trim_video_ffmpeg, trim_audio_ffmpeg
from utils.dropbox_utils import upload_to_dropbox
from utils.file_utils import cleanup_files, format_bytes
from config import BOT_TOKEN

bot = AsyncTeleBot(BOT_TOKEN)
download_queue = asyncio.Queue()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Message Utilities ---
async def send_message(chat_id, text):
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"Failed to send message: {e}")

# --- Main Download Processor ---
async def process_download(message, url, is_audio=False, trim=False, trim_audio=False, start_time=None, end_time=None):
    chat_id = message.chat.id
    try:
        platform = detect_platform(url)
        file_path = None
        file_paths = []

        # Platform-based processing
        if platform == "youtube":
            file_path = await process_youtube(url, is_audio)
        elif platform == "instagram":
            if re.search(r"/p/|/photo|/stories", url):
                file_paths = await process_instagram_image(url)
            else:
                file_path = await process_instagram(url)
        elif platform == "facebook":
            file_path = await process_facebook(url)
        elif platform == "twitter":
            file_path = await process_twitter(url)
        elif platform == "adult":
            file_path = await process_adult(url)
        else:
            await send_message(chat_id, "❌ Unsupported or unrecognized URL.")
            return

        # Audio extraction
        if is_audio and file_path:
            audio_path = await extract_audio_ffmpeg(file_path)
            cleanup_files([file_path])
            file_path = audio_path

        # Trimming logic
        if trim and file_path:
            trimmed_path = await trim_video_ffmpeg(file_path, start_time, end_time)
            cleanup_files([file_path])
            file_path = trimmed_path
        elif trim_audio and file_path:
            trimmed_audio = await trim_audio_ffmpeg(file_path, start_time, end_time)
            cleanup_files([file_path])
            file_path = trimmed_audio

        # Send file(s)
        if file_path:
            size = os.path.getsize(file_path)
            if size > 48 * 1024 * 1024:
                link = await upload_to_dropbox(file_path)
                await send_message(chat_id, f"File too large for Telegram. Download here:\n{link}")
            else:
                await bot.send_document(chat_id, open(file_path, "rb"))
            cleanup_files([file_path])

        elif file_paths:
            all_sent = True
            for path in file_paths:
                try:
                    size = os.path.getsize(path)
                    if size > 48 * 1024 * 1024:
                        all_sent = False
                        break
                    await bot.send_photo(chat_id, open(path, "rb"))
                except Exception as e:
                    logger.warning(f"Failed to send image: {e}")
                    all_sent = False

            if not all_sent:
                zip_link = await upload_to_dropbox(file_paths)
                await send_message(chat_id, f"Download all images here:\n{zip_link}")
            cleanup_files(file_paths)

    except Exception as e:
        logger.error(f"Error processing download: {e}")
        traceback.print_exc()
        await send_message(chat_id, "❌ Failed to process your request.")
    finally:
        gc.collect()

# --- Queue Worker ---
async def worker():
    while True:
        try:
            message, url, is_audio, trim, trim_audio, start_time, end_time = await download_queue.get()
            await process_download(message, url, is_audio, trim, trim_audio, start_time, end_time)
        except Exception as e:
            logger.error(f"Worker error: {e}")
        finally:
            download_queue.task_done()

# --- Bot Command Handlers ---
@bot.message_handler(commands=["start"])
async def handle_start(message):
    await send_message(message.chat.id, "👋 Welcome! Send me a video/image link to download.\nYou can also use /audio or /trim.")

@bot.message_handler(commands=["audio"])
async def handle_audio(message):
    try:
        url = message.text.split(" ", 1)[1].strip()
        await download_queue.put((message, url, True, False, False, None, None))
    except:
        await send_message(message.chat.id, "⚠️ Usage: /audio <video_url>")

@bot.message_handler(commands=["trim"])
async def handle_trim(message):
    try:
        parts = message.text.split(" ")
        url = parts[1]
        start_time = parts[2]
        end_time = parts[3]
        await download_queue.put((message, url, False, True, False, start_time, end_time))
    except:
        await send_message(message.chat.id, "⚠️ Usage: /trim <url> <start_time> <end_time>")

@bot.message_handler(commands=["trimAudio"])
async def handle_trim_audio(message):
    try:
        parts = message.text.split(" ")
        url = parts[1]
        start_time = parts[2]
        end_time = parts[3]
        await download_queue.put((message, url, False, False, True, start_time, end_time))
    except:
        await send_message(message.chat.id, "⚠️ Usage: /trimAudio <url> <start_time> <end_time>")

@bot.message_handler(func=lambda message: True)
async def handle_url(message):
    if "http" in message.text:
        await download_queue.put((message, message.text.strip(), False, False, False, None, None))
    else:
        await send_message(message.chat.id, "⚠️ Please send a valid URL or use /audio or /trim")

# --- Entry Point ---
if __name__ == "__main__":
    for _ in range(3):  # Adjust number of workers based on server capacity
        asyncio.create_task(worker())
    asyncio.run(bot.polling(non_stop=True))