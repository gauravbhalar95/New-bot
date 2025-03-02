import yt_dlp
import os
import logging
import gc
import asyncio
import subprocess
from config import DOWNLOAD_DIR, MAX_FILE_SIZE_MB
from utils.thumb_generator import generate_thumbnail
from utils.logger import setup_logging
from utils.streaming import get_streaming_url  # ✅ Streaming logic

# ✅ Initialize logger
logger = setup_logging(logging.DEBUG)

async def process_adult(url):
    """Downloads video, fetches streaming URL, and extracts a 1-min clip."""
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bv+ba/best[ext=mp4]/best',
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 5,
        'fragment_retries': 5,
        'continuedl': True,
        'buffer_size': '16K',
        'no_part': True,
        'nocheckcertificate': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://x.com/'
        }
    }

    # ✅ Initialize variables
    file_path = None
    file_size = 0
    streaming_url = None
    compressed_path = None
    best_scene_clip = None

    try:
        loop = asyncio.get_running_loop()

        # ✅ Run yt_dlp in a separate thread
        def download_video():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)

        info_dict = await loop.run_in_executor(None, download_video)

        if not info_dict or "requested_downloads" not in info_dict:
            logger.error("❌ No video found.")
            return None, None, None, None, None

        # ✅ Get file path safely
        file_path = info_dict["requested_downloads"][0]["filepath"]

        # ✅ Check if file exists before getting size
        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)

            # ✅ Check Telegram's limit from config
            if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                logger.warning(f"⚠️ File too large for Telegram ({MAX_FILE_SIZE_MB}MB limit). Returning streaming URL instead.")
                streaming_url = await get_streaming_url(url)  # ✅ Use streaming utils
                return None, None, streaming_url, None, None

            # ✅ Generate thumbnail asynchronously
            try:
                compressed_path = await generate_thumbnail(file_path)
            except Exception as thumb_error:
                logger.error(f"⚠️ Thumbnail generation failed: {thumb_error}")
                compressed_path = None  

            # ✅ Extract 1-minute best scene clip
            video_duration = info_dict.get("duration", 0)
            best_scene_clip = await extract_best_scene(file_path, video_duration)

            logger.info(f"✅ Download completed: {file_path} ({file_size / (1024 * 1024):.2f} MB)")
            logger.info(f"✅ Thumbnail generated: {compressed_path}")
            logger.info(f"✅ Best 1-min scene extracted: {best_scene_clip}")

            return file_path, file_size, streaming_url, compressed_path, best_scene_clip

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")

        # ✅ Use streaming_utils for fallback
        streaming_url = await get_streaming_url(url)
        if streaming_url:
            logger.info(f"✅ Streaming URL fetched: {streaming_url}")
            return None, None, streaming_url, None, None

    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")
    finally:
        gc.collect()  # ✅ Ensure garbage collection

    return None, None, None, None, None

async def extract_best_scene(video_path, duration):
    """Extracts a 1-minute scene from the best part of the video."""
    if not os.path.exists(video_path) or duration <= 60:
        return None  # Skip if duration is too short

    start_time = max(0, duration // 3)  # Start at 1/3rd of the video
    clip_path = os.path.join(DOWNLOAD_DIR, "best_scene.mp4")

    command = [
        "ffmpeg", "-i", video_path, "-ss", str(start_time),
        "-t", "60", "-c:v", "libx264", "-c:a", "aac",
        "-b:a", "128k", "-preset", "fast", clip_path, "-y"
    ]

    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return clip_path if process.returncode == 0 and os.path.exists(clip_path) else None