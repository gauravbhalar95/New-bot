import yt_dlp
import os
import telebot
import logging
from config import DOWNLOAD_DIR, API_TOKEN
from utils.thumb_generator import generate_thumbnail

# ✅ Initialize bot in webhook mode (no polling)
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_adult(url):
    """
    Downloads an adult video in HD, generates a thumbnail, and returns (file_path, streaming_url).
    """
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'best[ext=mp4]/best',
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'continuedl': True,
        'http_chunk_size': 1048576,
        'quiet': False,
        'nocheckcertificate': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://x.com/'
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            if not info_dict or "requested_downloads" not in info_dict:
                logger.error("❌ No video found.")
                return None, None

            file_path = info_dict["requested_downloads"][0]["filepath"]
            streaming_url = info_dict.get('url') or info_dict.get('webpage_url')

            if os.path.exists(file_path):
                logger.info(f"✅ Download completed: {file_path}")
                return file_path, streaming_url
            else:
                logger.error("⚠️ File not found after download.")
                return None, None

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")
    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")

    return None, None

# Example usage with multiple URLs
urls = [
    "https://www.xvideos.com/video12345/example-video-1",
    "https://www.pornhub.com/view_video.php?viewkey=ph5a8e5e2e8b7f1",
    "https://www.redtube.com/123456/example-video-3"
]

for url in urls:
    file_path, streaming_url = process_adult(url)

    if streaming_url:
        print(f"Streaming URL for {url}: {streaming_url}")
    elif file_path:
        print(f"Downloaded file for {url}: {file_path}")
        thumbnail_path = generate_thumbnail(file_path)
        print(f"Thumbnail generated at: {thumbnail_path}")
    else:
        print(f"Download failed for {url}.")