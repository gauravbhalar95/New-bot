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

# ✅ Download or get streaming link
def process_adult(url):
    """Download video or return streaming link."""
    try:
        ydl_opts = {
            'format': 'best',
            'noplaylist': True,
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info.get('url')  # ✅ Get direct streaming URL
            file_size = info.get('filesize', 0)  # ✅ Get file size if available
            file_name = info.get('title', 'video.mp4')

        return video_url, file_size, file_name
    except Exception:
        return None, None, None
