import yt_dlp
import os
import re
from config import FACEBOOK_FILE, DOWNLOAD_DIR
from utils.renamer import rename_files_in_directory
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging

# **Limit Filename Length to Prevent Errors**
def truncate_filename(filename, max_length=100):
    """Truncate the filename to prevent errors due to excessive length."""
    if len(filename) > max_length:
        return filename[:max_length].rsplit(' ', 1)[0]  # Avoid truncating in the middle of a word
    return filename

def process_facebook(url, output_dir=DOWNLOAD_DIR):
    """Downloads a Facebook video using cookies and saves it in the specified directory."""

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        with yt_dlp.YoutubeDL({"noprogress": True}) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            original_title = info_dict.get("title", "video")
            file_ext = info_dict.get("ext", "mp4")  # Default to 'mp4' if missing
    except Exception as e:
        return f"❌ Error extracting info: {str(e)}"

    # **Sanitize and Truncate the Filename**
    safe_title = sanitize_filename(original_title)
    truncated_title = truncate_filename(safe_title, 100)  # Limit to 100 chars
    filename = f"{truncated_title}.{file_ext}"

    # **Ensure Filename is Valid**
    filename = re.sub(r'[\/\\:*?"<>|]', "_", filename)  # Replace invalid characters

    # **Set yt-dlp options**
    options = {
        "outtmpl": os.path.join(output_dir, filename),
        "format": "bv+ba/b",
        "cookiefile": FACEBOOK_FILE,
        "merge_output_format": "mp4",
        "noprogress": False,  # 👈 Show Download Progress
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }]
    }

    try:
        # **Download the video and extract info**
        with yt_dlp.YoutubeDL(options) as ydl:
            info_dict = ydl.extract_info(url, download=True)  # 👈 FIX: Store info_dict

        # **Rename files after downloading**
        rename_files_in_directory(output_dir)

        return f"✅ Video '{info_dict['title']}' downloaded successfully in {output_dir}"

    except Exception as e:
        return f"❌ Download failed: {str(e)}"