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
    url_match = re.search(r"https?://[^\s]+", text)  # Extract URL using regex
    if url_match:
        url = url_match.group(0)
        parsed_url = urlparse(url)
        if parsed_url.scheme and parsed_url.netloc:
            return url  # Return only valid URLs
    return None

# ✅ Async Function for Downloading Videos
async def process_adult(text):
    url = extract_valid_url(text)
    if not url:
        logger.error("❌ Invalid URL provided.")
        return None, 0, None, None, None

    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bv+ba/b',
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
        },
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }]
    }

    file_path, file_size, streaming_url, thumbnail_path, clip_path = None, 0, None, None, None

    try:
        loop = asyncio.get_running_loop()

        # ✅ Try fetching the streaming URL first
        streaming_url = await get_streaming_url(url)

        # ✅ If no streaming URL, proceed with downloading
        if not streaming_url:
            def download_video():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=True)

            info_dict = await loop.run_in_executor(executor, download_video)

            if not info_dict or "requested_downloads" not in info_dict:
                logger.error("❌ No video found.")
                return None, 0, None, None, None

            downloads = info_dict.get("requested_downloads", [])
            if not downloads:
                logger.error("❌ No downloads found in response.")
                return None, 0, None, None, None

            file_path = downloads[0].get("filepath")

            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)

                # ✅ Check if file is too large for Telegram
                if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                    logger.warning(f"⚠️ File too large for Telegram ({MAX_FILE_SIZE_MB}MB limit). Returning streaming URL instead.")
                    return None, 0, streaming_url, None, None

                # ✅ Generate Thumbnail & Best Clip in Parallel
                thumbnail_task = asyncio.create_task(generate_thumbnail(file_path))
                clip_task = asyncio.create_task(download_best_clip(file_path, file_size))

                thumbnail_path, clip_path = await asyncio.gather(thumbnail_task, clip_task)

                logger.info(f"✅ Download completed: {file_path} ({file_size / (1024 * 1024):.2f} MB)")
                logger.info(f"✅ Thumbnail generated: {thumbnail_path}")
                logger.info(f"✅ Best clip downloaded: {clip_path}")

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")

    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")

    finally:
        gc.collect()

    return file_path, file_size, streaming_url, thumbnail_path, clip_path  # ✅ Ensure function always returns 5 values


# ✅ Function for 1-Minute Best Clip
async def download_best_clip(file_path, file_size):
    """Downloads a 1-minute best scene clip from the video."""
    clip_path = file_path.replace(".mp4", "_clip.mp4")

    start_time = max(0, (file_size // 4) // (1024 * 1024))
    command = [
        "ffmpeg", "-i", file_path, "-ss", str(start_time),
        "-t", "60", "-c:v", "libx264", "-c:a", "aac",
        "-b:a", "128k", "-preset", "ultrafast", clip_path, "-y"
    ]

    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode == 0 and os.path.exists(clip_path):
        return clip_path
    return None


# ✅ Function to Send Streaming, Thumbnail, Clip, and Video
async def send_streaming_options(bot, chat_id, text):
    """Handles streaming, thumbnail, clip, and full video sending in order."""

    try:
        # ✅ Ensure Correct Unpacking (5 values)
        file_path, file_size, streaming_url, thumbnail_path, clip_path = await process_adult(text)

        if not file_path and not streaming_url:
            await bot.send_message(chat_id, "⚠️ **Failed to fetch video or streaming link. Try again!**")
            return

        # ✅ Send Streaming Link First (If Available)
        if streaming_url:
            stream_message = f"🎬 **Streaming Link:**\n[▶ Watch Video]({streaming_url})"
            await bot.send_message(chat_id, stream_message, parse_mode="Markdown")

        # ✅ Send Thumbnail Next (If Available)
        if thumbnail_path and os.path.exists(thumbnail_path):
            with open(thumbnail_path, "rb") as thumb:
                await bot.send_photo(chat_id, thumb, caption="📸 **Thumbnail**")

        # ✅ Send Best Clip Next (If Available)
        if clip_path and os.path.exists(clip_path):
            with open(clip_path, "rb") as clip:
                await bot.send_video(chat_id, clip, caption="🎞 **Best 1-Min Scene Clip!**")
            os.remove(clip_path)  # ✅ Delete Clip After Sending

        # ✅ Send Full Video Last (If Available)
        if file_path and os.path.exists(file_path):
            with open(file_path, "rb") as video:
                await bot.send_video(chat_id, video, caption="📹 **Full Video Downloaded!**")

    except Exception as e:
        logger.error(f"⚠️ Error in send_streaming_options: {e}")
        await bot.send_message(chat_id, "⚠️ **An error occurred while processing your request.**")
