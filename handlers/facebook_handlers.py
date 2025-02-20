import yt_dlp
import os
from config import FACEBOOK_FILE
from utils.sanitize import sanitize_filename
from utils.renamer import rename_files_in_directory

def process_facebook(video_url, output_dir="downloads"):
    """Downloads a Facebook video using cookies and saves it in the specified directory."""
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    options = {
        "outtmpl": f"{output_dir}/%(title)s.%(ext)",  # Save with original title
        "format": "best",
        "cookies": FACEBOOK_FILE,
        "merge_output_format": "mp4",
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }]
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info_dict = ydl.extract_info(video_url, download=False)
        original_title = info_dict.get("title", "video")
        
        # **Sanitize the filename to prevent errors**
        safe_title = sanitize_filename(original_title)
        options["outtmpl"] = f"{output_dir}/{safe_title}.%(ext)s"

        # **Download the video**
        ydl.download([video_url])

    # **Call the renamer function after download**
    rename_files_in_directory(output_dir)

    return f"Video downloaded and renamed successfully in {output_dir}"