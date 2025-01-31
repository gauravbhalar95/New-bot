import os
from yt_dlp import YoutubeDL
from config import DOWNLOAD_DIR

def download_video(url):
    """
    Download a video using yt-dlp.
    Returns the file path and file size.
    """
    ydl_opts = {
        'format': 'best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'quiet': True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            file_size = os.path.getsize(file_path)
            return file_path, file_size
    except Exception as e:
        print(f"Error downloading video: {e}")
        return None, None