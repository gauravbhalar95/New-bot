import os
import sys
import subprocess
import yt_dlp
import logging
from utils.sanitize import sanitize_filename
from config import YOUTUBE_FILE, DOWNLOAD_DIR
from utils.logger import setup_logging

# Logger Initialization
logger = setup_logging(logging.DEBUG)

# Ensure the download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def process_youtube(youtube_url, start_time, end_time):
    """Download a YouTube video with audio and trim it using FFmpeg."""
    
    ydl_opts = {
        'format': 'bv*+ba/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        'merge_output_format': 'mp4',
        'retries': 5,
        'logger': logger,
        'quiet': True,
    }

    try:
        # Download video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(youtube_url, download=True)
            if not info_dict:
                logger.error("Download failed: No info_dict returned.")
                return None

            video_filename = ydl.prepare_filename(info_dict).replace('.webm', '.mp4')
            trimmed_filename = video_filename.replace('.mp4', '_trimmed.mp4')

            # Trim using FFmpeg
            ffmpeg_cmd = [
                'ffmpeg', '-y', '-i', video_filename,
                '-ss', start_time, '-to', end_time, '-c:v', 'copy', '-c:a', 'copy', trimmed_filename
            ]
            subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Cleanup: Delete original file
            if os.path.exists(trimmed_filename):
                os.remove(video_filename)
                logger.info(f"Trimmed video saved: {trimmed_filename}")
                return trimmed_filename
            else:
                logger.error("Error trimming video.")
                return None
    except Exception as e:
        logger.error(f"Error downloading and trimming video: {e}")
        return None


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python script.py <YouTube_URL> <Start_Time> <End_Time>")
        sys.exit(1)

    youtube_url = sys.argv[1]
    start_time = sys.argv[2]  # Format: HH:MM:SS
    end_time = sys.argv[3]    # Format: HH:MM:SS

    trimmed_video = download_and_trim_video(youtube_url, start_time, end_time)
    if trimmed_video:
        print(f"✅ Trimmed Video Saved: {trimmed_video}")
    else:
        print("❌ Failed to process the video.")