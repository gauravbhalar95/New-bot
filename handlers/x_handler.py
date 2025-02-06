import yt_dlp
import os
from config import DOWNLOAD_DIR, COOKIES_FILE

def download_twitter_media(url):
    """Downloads a Twitter/X video and returns (file_path, file_size)."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # Define the output filename
    output_path = os.path.join(DOWNLOAD_DIR, "twitter_video.%(ext)s")

    # Base options
    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'quiet': False  # Set to False for debugging
    }

    # Add cookies only if the file exists
    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Ensure valid response
            if not info:
                print("❌ Error: No video information found.")
                return None

            # Get downloaded file path
            downloaded_files = ydl.prepare_filename(info)
            file_path = downloaded_files.replace("%(ext)s", "mp4")

            # Validate file existence
            if not os.path.exists(file_path):
                print(f"❌ Error: File not found - {file_path}")
                return None

            file_size = os.path.getsize(file_path)
            return file_path, file_size

    except Exception as e:
        print(f"⚠️ Twitter Download Error: {e}")
        return None