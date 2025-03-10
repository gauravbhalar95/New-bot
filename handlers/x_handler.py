import os
import asyncio
import yt_dlp
import subprocess
import logging
from utils.logger import setup_logging
from config import DOWNLOAD_DIR, X_FILE

# Initialize logger
logger = setup_logging(logging.DEBUG)

async def download_twitter_media(url):
    """
    Downloads a Twitter/X video using yt-dlp.
    Falls back to twdl only if yt-dlp crashes without an error message.
    """
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bv+ba/b',
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'cookiefile': X_FILE,
        'continuedl': True,
        'http_chunk_size': 1048576,  # 1 MB chunk size
        'quiet': False,
        'nocheckcertificate': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://x.com/'
        }
    }

    try:
        loop = asyncio.get_running_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await loop.run_in_executor(None, ydl.extract_info, url, True)

            if not info_dict or "requested_downloads" not in info_dict:
                logger.error("❌ yt-dlp: No video found.")
                return None, None  # Don't fall back to twdl

            file_path = info_dict["requested_downloads"][0]["filepath"]
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            logger.info(f"✅ yt-dlp: Download completed: {file_path}")
            return file_path, file_size

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ yt-dlp failed with an error: {e}")
        return None, None  # Don't use twdl if yt-dlp returned an error

    except Exception as e:
        logger.warning(f"⚠️ yt-dlp crashed unexpectedly: {e}")
        logger.info("🔄 Falling back to twdl...")

        # Try using twdl as a fallback
        try:
            process = subprocess.run(
                ["twdl", "-o", DOWNLOAD_DIR, url],
                capture_output=True, text=True, check=True
            )
            output = process.stdout

            for line in output.split("\n"):
                if line.endswith(".mp4"):
                    file_path = os.path.join(DOWNLOAD_DIR, line.strip())
                    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                    logger.info(f"✅ twdl: Download completed: {file_path}")
                    return file_path, file_size

        except subprocess.CalledProcessError as twdl_error:
            logger.error(f"❌ twdl also failed: {twdl_error}")

    return None, None