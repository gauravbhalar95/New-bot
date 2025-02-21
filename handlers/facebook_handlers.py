import yt_dlp
import os
import re
from config import FACEBOOK_FILE, DOWNLOAD_DIR
from utils.renamer import rename_files_in_directory
from utils.sanitize import is_valid_url  # Sanitization utility
def process_facebook(url, output_dir="downloads"):
    """Downloads a Facebook video using cookies and saves it in the specified directory."""
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        original_title = info_dict.get("title", "video")
        file_ext = info_dict.get("ext", "mp4")  # Default to 'mp4' if missing

    # **Sanitize and truncate the filename**
    safe_title = sanitize_filename(original_title)
    filename = f"{safe_title}.{file_ext}"

    # **Set yt-dlp options**
    options = {
        "outtmpl": f"{output_dir}/{filename}",
        "format": "best",
        "cookies": FACEBOOK_FILE,
        "merge_output_format": "mp4",
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }]
    }

    # **Download the video**
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])

    # **Rename files after downloading**
    rename_files_in_directory(output_dir)

    return f"Video downloaded and renamed successfully in {output_dir}"