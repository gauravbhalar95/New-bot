import yt_dlp
import os
import logging
import gc
import asyncio
import subprocess
import re
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from config import DOWNLOAD_DIR, MAX_FILE_SIZE_MB, COOKIES_FILE
from utils.thumb_generator import generate_thumbnail
from utils.logger import setup_logging
from utils.streaming import get_streaming_url

# ✅ Logging Setup
logger = setup_logging(logging.DEBUG)

# ✅ ThreadPool for Faster Execution
executor = ThreadPoolExecutor(max_workers=5)

# ✅ Function to Extract and Validate URL
def extract_valid_url(text):
    url_match = re.search(r"https?://[^\s]+", text)
    if url_match:
        url = url_match.group(0)
        parsed_url = urlparse(url)
        if parsed_url.scheme and parsed_url.netloc:
            return url
    return None

async def process_adult(text):
    url = extract_valid_url(text)
    if not url:
        logger.error("❌ Invalid URL provided.")
        return None, 0, None, None, None, None

    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bv+ba/best',
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 5,
        'fragment_retries': 5,
        'continuedl': True,
        'buffer_size': '32K',
        'no_part': True,
        'nocheckcertificate': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': url,
            'Accept-Language': 'en-US,en;q=0.9'
        }
    }

    try:
        loop = asyncio.get_running_loop()

        # ✅ Fetch Streaming URL
        streaming_url = await get_streaming_url(url)

        def download_video():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)  # Don't Download, just get URL

        info_dict = await loop.run_in_executor(executor, download_video)

        if not info_dict or "url" not in info_dict:
            return None, 0, streaming_url, None, None, None

        download_url = info_dict.get("url")  # ✅ Extract Direct Download Link

        return None, 0, streaming_url, None, None, download_url

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")

    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")

    finally:
        gc.collect()

    return None, 0, None, None, None, None


# ✅ Function for 1-Minute Best Clip
async def download_best_clip(file_path, file_size):
    clip_path = file_path.replace(".mp4", "_clip.mp4")
    start_time = max(0, (file_size // 4) // (1024 * 1024))
    
    command = [
        "ffmpeg", "-i", file_path, "-ss", str(start_time),
        "-t", "60", "-c:v", "libx264", "-c:a", "aac",
        "-b:a", "128k", "-preset", "ultrafast", clip_path, "-y"
    ]

    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return clip_path if process.returncode == 0 and os.path.exists(clip_path) else None

async def send_media(bot, chat_id, text):
    try:
        file_path, file_size, streaming_url, thumbnail_path, clip_path, download_url = await process_adult(text)

        if not streaming_url and not download_url:
            await bot.send_message(chat_id, "⚠️ **Failed to fetch video or streaming link. Try again!**")
            return

        message = "🎬 **Streaming & Download Links:**\n"
        
        if streaming_url:
            message += f"▶ **Watch Online:** [Click Here]({streaming_url})\n"
        
        if download_url:
            message += f"📥 **Download High Quality:** [Click Here]({download_url})"

        await bot.send_message(chat_id, message, parse_mode="Markdown")

        if thumbnail_path and os.path.exists(thumbnail_path):
            with open(thumbnail_path, "rb") as thumb:
                await bot.send_photo(chat_id, thumb, caption="📸 **Thumbnail**")

        if clip_path and os.path.exists(clip_path):
            with open(clip_path, "rb") as clip:
                await bot.send_video(chat_id, clip, caption="🎞 **Best 1-Min Scene Clip!**")
            os.remove(clip_path)

        if file_path and os.path.exists(file_path):
            with open(file_path, "rb") as video:
                await bot.send_video(chat_id, video, caption="📹 **Full Video Downloaded!**")

    except Exception as e:
        logger.error(f"⚠️ Error in send_media: {e}")
        await bot.send_message(chat_id, "⚠️ **An error occurred while processing your request.**")