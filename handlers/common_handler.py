import os
import telebot
import yt_dlp
import logging
from config import API_TOKEN, DOWNLOAD_DIR
from utils.thumb_generator import generate_thumbnail

# Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Max download size in bytes
MAX_DOWNLOAD_SIZE = 100 * 1024 * 1024  # 100MB limit

def process_adult(video_path, chat_id):
    """Download video if it's small; otherwise, return streaming link, and send thumbnail."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # Output path for downloading videos
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'mp4/best',  # Best quality in mp4 format
        'noplaylist': True,    # Don't download playlists
        'socket_timeout': 10,
        'retries': 5,
        'quiet': False,
        'nocheckcertificate': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        },
        'verbose': True
    }

    try:
        # Extract video information without downloading
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info.get('url')  # Streaming URL
            file_size = info.get('filesize') or 0  # File size
            file_name = info.get('title', 'video.mp4')  # Default title if none provided
            thumbnail = info.get('thumbnail')  # Thumbnail

        # If video size is within limit, download the video
        if file_size and file_size <= MAX_DOWNLOAD_SIZE:
            ydl_opts['outtmpl'] = file_name  # Update output filename
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Generate thumbnail after video download
            file_path = os.path.join(DOWNLOAD_DIR, file_name)
            thumbnail_path = generate_thumbnail(file_path)
            logger.info(f"Thumbnail generated: {thumbnail_path}")

            # Send thumbnail before sending the video
            if os.path.exists(thumbnail_path):
                with open(thumbnail_path, 'rb') as thumb:
                    bot.send_photo(chat_id, thumb, caption="✅ Here's the thumbnail!")

            return file_path, file_size, thumbnail_path, True  # Return success

        # Return streaming link if video is too large
        return video_url, file_size, thumbnail, False

    except yt_dlp.DownloadError as e:
        logger.error(f"Download failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

    return None, None, None, None  # Return None in case of failure