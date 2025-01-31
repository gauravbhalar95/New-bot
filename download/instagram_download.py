import yt_dlp
import os
import re

# Directory to store downloads
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Authentication details
COOKIES_FILE = "cookies.txt"  # Ensure this file is up-to-date
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")  # Set this in your environment
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")  # Set this in your environment

# Utility to sanitize filenames
def sanitize_filename(filename, max_length=250):
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    return filename.strip()[:max_length]

# Function to download Instagram video
def download_instagram_video(url):
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'socket_timeout': 10,
        'retries': 5,
    }

    # Use cookies if available, otherwise use username & password
    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE
    elif INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD:
        ydl_opts["username"] = INSTAGRAM_USERNAME
        ydl_opts["password"] = INSTAGRAM_PASSWORD
    else:
        print("Warning: No authentication method found. Private videos may fail.")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            file_size = info_dict.get("filesize", 0)
            return file_path, file_size
    except Exception as e:
        print(f"Error downloading Instagram video: {e}")
        return None, 0

# Function to fetch Instagram streaming URL
def get_instagram_streaming_url(url):
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
    }

    # Use authentication if required
    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE
    elif INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD:
        ydl_opts["username"] = INSTAGRAM_USERNAME
        ydl_opts["password"] = INSTAGRAM_PASSWORD

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            return info_dict.get("url")
    except Exception as e:
        print(f"Error fetching Instagram streaming URL: {e}")
        return None
