import yt_dlp
import os
import logging
import gc
import asyncio
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

# ✅ Function to Extract and Validate URL
def extract_valid_url(text):
    url_match = re.search(r"https?://[^\s]+", text)  # Extract URL using regex
    if url_match:
        url = url_match.group(0)
        parsed_url = urlparse(url)
        if parsed_url.scheme and parsed_url.netloc:
            return url  # Return only valid URLs
    return None

# ✅ Async Function for Downloading Videos with Streaming & Download Links
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

    file_path, file_size, streaming_url, download_url, thumbnail_path, clip_path = None, 0, None, None, None, None

    try:
        loop = asyncio.get_running_loop()

        # ✅ Fetch Streaming URL First
        streaming_url = await get_streaming_url(url)

        # ✅ If no streaming URL, proceed with downloading
        if not streaming_url:
            def fetch_video_info():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)

            video_info = await loop.run_in_executor(executor, fetch_video_info)
            
            # ✅ Extract direct download URL from video metadata
            download_url = video_info.get("url", None)

            estimated_size = sum(f.get('filesize', 0) for f in video_info.get('requested_formats', []))

            # ✅ Check if the estimated file size exceeds Telegram's limit
            if estimated_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                logger.warning(f"⚠️ File too large for Telegram ({MAX_FILE_SIZE_MB}MB limit). Returning streaming & download links instead.")
                return None, 0, streaming_url, download_url, None, None

            def download_video():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=True)

            info_dict = await loop.run_in_executor(executor, download_video)

            if not info_dict or "requested_downloads" not in info_dict:
                logger.error("❌ No video found.")
                return None, 0, None, None, None, None

            downloads = info_dict.get("requested_downloads", [])
            if not downloads:
                logger.error("❌ No downloads found in response.")
                return None, 0, None, None, None, None

            file_path = downloads[0].get("filepath")

            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)

                # ✅ Parallel Processing: Generate Thumbnail & Best Clip
                thumbnail_task = generate_thumbnail(file_path)
                clip_task = download_best_clip(file_path, file_size)
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

    return file_path, file_size, streaming_url, download_url, thumbnail_path, clip_path  # ✅ Now returns 6 values