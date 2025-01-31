import os
import yt_dlp

# Output directory for downloads
OUTPUT_DIR = "downloads"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Function to download video from XVideos
def download_xvideo(url):
    """
    Downloads a video from XVideos using yt-dlp.
    
    :param url: The XVideos URL
    :return: Tuple (file_path, file_size) or (None, None) on failure
    """
    try:
        ydl_opts = {
            "format": "best",
            "outtmpl": f"{OUTPUT_DIR}/%(title)s.%(ext)s",
            "noplaylist": True,
            "quiet": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        return file_path, file_size

    except Exception as e:
        print(f"❌ Error downloading video: {e}")
        return None, None

# Function to get streaming link
def get_xvideo_stream(url):
    """
    Fetches a streaming URL from XVideos using yt-dlp.
    
    :param url: The XVideos URL
    :return: Streaming URL or None
    """
    try:
        ydl_opts = {
            "quiet": True,
            "noplaylist": True,
            "skip_download": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get("url")

    except Exception as e:
        print(f"❌ Error getting streaming URL: {e}")
        return None
