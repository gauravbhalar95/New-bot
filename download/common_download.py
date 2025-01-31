import yt_dlp
import os
import re

# Directory to store downloads
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Cookies file for authentication
COOKIES_FILE = "cookies.txt"  # Ensure this file is up-to-date

# Supported domains
SUPPORTED_DOMAINS = [
    'x.com',
    'facebook.com', 'xnxx.com', 'xhamster.com', 'pornhub.com'
]

# Utility to sanitize filenames
def sanitize_filename(filename, max_length=250):
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    return filename.strip()[:max_length]

# Function to download a video from any supported platform
def download_video(url):
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'socket_timeout': 10,
        'retries': 5,
    }

    # Use cookies if available
    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE

    # Detect domain
    domain = next((d for d in SUPPORTED_DOMAINS if d in url), None)
    if not domain:
        print("Unsupported domain.")
        return None, 0

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            file_size = info_dict.get("filesize", 0)
            return file_path, file_size
    except Exception as e:
        print(f"Error downloading video from {domain}: {e}")
        return None, 0

# Function to fetch a direct streaming URL
def get_streaming_url(url):
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
    }

    # Use cookies if available
    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            return info_dict.get("url")
    except Exception as e:
        print(f"Error fetching streaming URL: {e}")
        return None
