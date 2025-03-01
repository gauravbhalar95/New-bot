import yt_dlp
import os
import logging
import gc
import asyncio
from config import DOWNLOAD_DIR
from utils.thumb_generator import generate_thumbnail
from utils.logger import setup_logging

# ✅ Initialize logger
logger = setup_logging(logging.DEBUG)

# ✅ Async function for downloading videos
async def process_adult(url):
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bv+ba/b',
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

    # ✅ Initialize variables to prevent access errors
    file_path = None
    file_size = 0
    streaming_url = None  # 🔴 This will store fallback streaming URL

    try:
        loop = asyncio.get_running_loop()

        # ✅ Run yt_dlp in a separate thread
        def download_video():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)

        info_dict = await loop.run_in_executor(None, download_video)

        if not info_dict or "requested_downloads" not in info_dict:
            logger.error("❌ No video found.")
            return None, None, None

        # ✅ Get file path safely
        file_path = info_dict["requested_downloads"][0]["filepath"]

        # ✅ Check if file exists before getting size
        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)

            # ✅ Generate thumbnail asynchronously
            thumbnail_path = await generate_thumbnail(file_path)

            logger.info(f"✅ Download completed: {file_path} ({file_size / (1024 * 1024):.2f} MB)")
            logger.info(f"✅ Thumbnail generated: {thumbnail_path}")

            return file_path, file_size, thumbnail_path

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")

        # ✅ If download fails, try fetching the streaming URL
        try:
            def get_stream_url():
                stream_opts = {
                    'format': 'bv+ba/b',
                    'noplaylist': True,
                    'nocheckcertificate': True,
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                        'Referer': 'https://x.com/'
                    }
                }
                with yt_dlp.YoutubeDL(stream_opts) as ydl:
                    return ydl.extract_info(url, download=False)

            stream_info = await loop.run_in_executor(None, get_stream_url)

            if stream_info and 'url' in stream_info:
                streaming_url = stream_info['url']
                logger.info(f"✅ Streaming URL fetched: {streaming_url}")
                return None, None, streaming_url  # 🔴 Returning streaming URL instead

        except Exception as stream_error:
            logger.error(f"⚠️ Failed to fetch streaming URL: {stream_error}")

    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")
    finally:
        gc.collect()  # ✅ Ensure garbage collection

    return None, None, None