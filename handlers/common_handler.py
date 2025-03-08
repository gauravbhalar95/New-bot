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
from mega import Mega  # ✅ Added Mega for cloud upload

# ✅ Logging Setup
logger = setup_logging(logging.DEBUG)

# ✅ ThreadPool for Faster Execution
executor = ThreadPoolExecutor(max_workers=5)

# ✅ Mega.nz Login (Replace with your credentials)
mega = Mega()
mega_email = "gauravbhalara95@gmail.com"
mega_password = "Gaurav74$"
m = mega.login(mega_email, mega_password)

# ✅ Function to Extract and Validate URL
def extract_valid_url(text):
    url_match = re.search(r"https?://[^\s]+", text)
    return url_match.group(0) if url_match else None

# ✅ Async Function for Downloading Videos
async def process_adult(text):
    url = extract_valid_url(text)
    if not url:
        logger.error("❌ Invalid URL provided.")
        return None, None  # Returning (streaming_url, download_link)

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

    file_path, streaming_url, download_link = None, None, None

    try:
        loop = asyncio.get_running_loop()

        # ✅ Fetch Streaming URL First
        streaming_url, download_url = await get_streaming_url(url)

        # ✅ If no streaming URL, proceed with downloading
        if not streaming_url:
            def download_video():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=True)

            info_dict = await loop.run_in_executor(executor, download_video)

            if not info_dict or "requested_downloads" not in info_dict:
                logger.error("❌ No video found.")
                return None, None

            downloads = info_dict.get("requested_downloads", [])
            if not downloads:
                logger.error("❌ No downloads found in response.")
                return None, None

            file_path = downloads[0].get("filepath")

            if file_path and os.path.exists(file_path):
                # ✅ Upload to Mega & Get Download Link
                file = m.upload(file_path)
                public_url = m.get_upload_link(file)

                logger.info(f"✅ Video uploaded: {public_url}")
                download_link = public_url

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")

    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")

    finally:
        gc.collect()

    return streaming_url, download_link  # ✅ Ensure function always returns streaming & full download link

# ✅ Function to Send Streaming & Full Video Download Link
async def send_streaming_options(bot, chat_id, text):
    """Handles streaming and full video download link sending."""

    try:
        streaming_url, download_link = await process_adult(text)

        if not streaming_url and not download_link:
            await bot.send_message(chat_id, "⚠️ **Failed to fetch video or download link. Try again!**")
            return

        message = ""

        # ✅ Send Streaming Link First (If Available)
        if streaming_url:
            message += f"🎬 **Streaming Link:**\n[▶ Watch Video]({streaming_url})\n\n"

        # ✅ Send Full Video Download Link (If Available)
        if download_link:
            message += f"📥 **Download Link:**\n[⬇ Click Here to Download]({download_link})"

        await bot.send_message(chat_id, message, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"⚠️ Error in send_streaming_options: {e}")
        await bot.send_message(chat_id, "⚠️ **An error occurred while processing your request.**")