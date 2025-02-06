import os
import telebot
import yt_dlp
import cloudscraper
from config import API_TOKEN  # ✅ Import API Token

# ✅ Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

# ✅ CloudScraper settings
scraper = cloudscraper.create_scraper()

# ✅ Supported adult sites
SUPPORTED_SITES = [
    "xvideos.com", "xnxx.com", "xhamster.com", "pornhub.com",
    "redtube.com", "tube8.com", "spankbang.com"
]

# ✅ Define max download size (in bytes)
MAX_DOWNLOAD_SIZE = 100 * 1024 * 1024  # 100MB limit

# ✅ Download or get streaming link
def process_adult(url):
    """Download video if it's small; otherwise, return streaming link."""
    try:
    ydl_opts = {
        'outtmpl': output_path,
        'format': 'mp4/best',
        'noplaylist': True,
        'socket_timeout': 10,
        'retries': 5,
        'quiet': False,
        'nocheckcertificate': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            
        }
    }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info.get('url')  # ✅ Get direct streaming URL
            file_size = info.get('filesize') or 0  # ✅ Handle None case
            file_name = info.get('title', 'video.mp4')
            thumbnail = info.get('thumbnail')  # ✅ Get video thumbnail

        if file_size and file_size <= MAX_DOWNLOAD_SIZE:
            # ✅ Download the video
            ydl_opts['outtmpl'] = file_name
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return file_name, file_size, thumbnail, True  # ✅ Downloaded

        return video_url, file_size, thumbnail, False  # ✅ Streaming link

    except Exception as e:
        print(f"Error processing URL: {url} - {e}")
        return None, None, None, None