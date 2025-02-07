import os
import telebot
import yt_dlp
import logging
from config import API_TOKEN, DOWNLOAD_DIR
from utils.thumb_generator import generate_thumbnail  

# ✅ Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

# ✅ Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Maximum file size limit (100MB)
MAX_DOWNLOAD_SIZE = 1000 * 1024 * 1024  

def process_adult(url, chat_id):
    """Downloads an adult video, generates a thumbnail, and sends a streaming link if too large."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    output_template = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_template,
        'format': 'best[ext=mp4]/best',  
        'noplaylist': True,
        'socket_timeout': 30,  
        'retries': 10,  
        'fragment_retries': 10,  
        'continuedl': True,  
        'http_chunk_size': 1048576,  
        'quiet': False,
        'nocheckcertificate': True,
        'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

            # ✅ Debugging: Print response from yt-dlp
            print("INFO DICT:", info_dict)  

            if not info_dict:
                logger.error("❌ No video found.")
                return None, None, None, None

            # ✅ Extract streaming link correctly
            video_url = None
            if "url" in info_dict:
                video_url = info_dict["url"]
            elif "entries" in info_dict and len(info_dict["entries"]) > 0:
                video_url = info_dict["entries"][0].get("url")

            file_path = info_dict.get("requested_downloads", [{}])[0].get("filepath")

            if not file_path or not os.path.exists(file_path):
                logger.warning(f"⚠️ Download failed. Returning streaming link: {video_url}")
                return None, None, None, video_url  # Return streamable link

            file_size = os.path.getsize(file_path)

            # ✅ If file size exceeds limit, return stream link instead
            if file_size > MAX_DOWNLOAD_SIZE:
                logger.warning(f"⚠️ File too large ({file_size} bytes). Sending streaming link instead.")
                return None, file_size, None, video_url  

            # ✅ Generate and send thumbnail
            thumbnail_path = generate_thumbnail(file_path)
            if os.path.exists(thumbnail_path):
                with open(thumbnail_path, 'rb') as thumb:
                    bot.send_photo(chat_id, thumb, caption="✅ Here's the thumbnail!")

            return file_path, file_size, thumbnail_path, None  # Return downloaded file

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")
    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")

    return None, None, None, None