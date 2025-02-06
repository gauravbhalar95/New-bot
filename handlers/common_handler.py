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
    """Download video or return streaming link with thumbnail."""
    try:
        ydl_opts = {
            'format': 'best',
            'noplaylist': True,
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info.get('url')  # ✅ Get direct streaming URL
            file_size = info.get('filesize') or 0  # ✅ Handle None case
            file_name = info.get('title', 'video.mp4')
            thumbnail_url = info.get('thumbnail')  # ✅ Get large thumbnail URL

        return video_url, file_size, file_name, thumbnail_url
    except Exception as e:
        print(f"Error processing URL: {url} - {e}")
        return None, None, None, None

# ✅ Example usage
if __name__ == "__main__":
    test_url = "https://www.xvideos.com/video123456/test-video"
    video_url, file_size, file_name, thumbnail = process_adult(test_url)
    
    if video_url:
        print(f"🎥 Video URL: {video_url}")
        print(f"📂 File Name: {file_name}")
        print(f"📦 File Size: {file_size} bytes")
        print(f"🖼️ Thumbnail: {thumbnail}")  # ✅ Large Thumbnail URL