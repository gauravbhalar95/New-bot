import yt_dlp
import os
from config import FACEBOOK_FILE
from utils.sanitize import sanitize_filename

def process_facebook(video_url, output_dir="downloads"):
    """Downloads a Facebook video using cookies and saves it in the specified directory."""
    options = {
        "outtmpl": f"{output_dir}/%(title)s.%(ext)s",  # Save with original title
        "format": "best",  # Best video-only + best audio-only OR best combined format
        "cookies": FACEBOOK_FILE,  # Use Facebook cookies
        "merge_output_format": "mp4",  # Ensure MP4 format
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }]
    }

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([video_url])

    return f"Video downloaded successfully in {output_dir}"

