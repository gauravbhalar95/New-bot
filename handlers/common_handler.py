import yt_dlp
import os
import logging
import gc
import asyncio
import subprocess
import re
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from config import DOWNLOAD_DIR, MAX_FILE_SIZE_MB
from utils.thumb_generator import generate_thumbnail
from utils.logger import setup_logging
from utils.streaming import get_streaming_url, ApiVideoClient, download_best_clip



# ✅ Logging Setup
logger = setup_logging(logging.DEBUG)

# ✅ ThreadPool for Faster Execution
executor = ThreadPoolExecutor(max_workers=5)

# ✅ Extract and Validate URL
def extract_valid_url(text):
    url_match = re.search(r"https?://[^\s]+", text)
    if url_match:
        url = url_match.group(0)
        parsed_url = urlparse(url)
        if parsed_url.scheme and parsed_url.netloc:
            return url
    return None

# ✅ Async Function to Process Videos
async def process_adult(text):
    url = extract_valid_url(text)
    if not url:
        logger.error("❌ Invalid URL provided.")
        return None, 0, None, None, None, None

    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bv+ba/b',
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 5,
        'continuedl': True,
        'no_part': True,
        'nocheckcertificate': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0',
            'Referer': url
        },
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }]
    }

    file_path, file_size, streaming_url, download_url, thumbnail_path, clip_path = None, 0, None, None, None, None

    try:
        loop = asyncio.get_running_loop()

        # ✅ Try fetching streaming & download links from `api.video`
        api_client = ApiVideoClient()
        video_links = await api_client.get_video_links()
        
        for video in video_links:
            if url in video['streaming_link']:
                streaming_url = video['streaming_link']
                download_url = video['download_link']
                break

        # ✅ If streaming URL is found, use it instead of downloading
        if streaming_url:
            logger.info(f"✅ Streaming Link Found: {streaming_url}")
            
            # ✅ Fetch the best 1-minute clip from `api.video`
            clip_path = await download_best_clip(download_url)
            
            return None, 0, streaming_url, download_url, None, clip_path

        # ✅ Otherwise, download using `yt-dlp`
        def download_video():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)

        info_dict = await loop.run_in_executor(executor, download_video)

        if not info_dict or "requested_downloads" not in info_dict:
            logger.error("❌ No video found.")
            return None, 0, None, None, None, None

        downloads = info_dict.get("requested_downloads", [])
        if not downloads:
            logger.error("❌ No downloads found.")
            return None, 0, None, None, None, None

        file_path = downloads[0].get("filepath")

        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)

            # ✅ If file is too large, only return streaming URL
            if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                logger.warning(f"⚠️ File too large for Telegram ({MAX_FILE_SIZE_MB}MB limit). Returning streaming link only.")
                return None, 0, streaming_url, download_url, None, None

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

    return file_path, file_size, streaming_url, download_url, thumbnail_path, clip_path

 