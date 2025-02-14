import gc
import os
import subprocess
import yt_dlp
import logging
from config import YOUTUBE_FILE, DOWNLOAD_DIR
import platform

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def sanitize_filename(name):
    """Sanitize the filename by removing or replacing invalid characters."""
    return "".join(c for c in name if c.isalnum() or c in (' ', '.', '_')).rstrip()

def process_youtube(url):
    """Download video using yt-dlp."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)  # Ensure download directory exists
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        'socket_timeout': 10,
        'retries': 5,
        'logger': logger,
        'verbose': True,
    }
    try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        if info_dict is None:
            logger.error("No info_dict returned. Download failed.")
            return None, 0
        return ydl.prepare_filename(info_dict), info_dict.get('filesize', 0)
except Exception as e:
    logger.error(f"Error downloading video: {e}")
    return None, 0

def trim_video(video_filename, start_time, end_time):
    """Trim video using FFmpeg."""
    trimmed_filename = f"{DOWNLOAD_DIR}/trimmed_{os.path.basename(video_filename)}"
    ffmpeg_cmd = [
        "ffmpeg", "-i", video_filename, "-ss", start_time, "-to", end_time,
        "-c", "copy", trimmed_filename, "-y"
    ]
    try:
        subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if os.path.exists(trimmed_filename):
            os.remove(video_filename)  # Delete original if trimming succeeded
            return trimmed_filename, os.path.getsize(trimmed_filename)
        else:
            logger.error("Trimming failed")
            return None, 0
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e}")
        return None, 0

def process_youtube_full(url, start_time=None, end_time=None):
    """Downloads and trims a YouTube video if start and end times are provided."""
    video_filename, file_size = process_youtube(url)
    if not video_filename:
        return None, 0
    if start_time and end_time:
        return trim_video(video_filename, start_time, end_time)
    return video_filename, file_size

def handle_message(url, start_time=None, end_time=None):
    """Handles incoming messages and processes YouTube links."""
    try:
        result = process_youtube_full(url, start_time, end_time)
        if result and result[0]:
            logger.info(f"Video processed successfully: {result[0]}, Size: {result[1]} bytes")
        else:
            logger.error("Failed to process video.")
    except Exception as e:
        logger.error(f"⚠️ Error processing request: {e}")

def clear_memory():
    """Memory clearing code using garbage collection and system cache flush (Linux only)."""
    print("Running garbage collection...")
    gc.collect()
    if platform.system() == "Linux":
        print("Clearing system caches...")
        os.system('sync; echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null')
    else:
        print("System cache clearing is only supported on Linux systems.")

if __name__ == "__main__":
    print("Starting YouTube processing and memory clearing process...")
    # Example usage (uncomment to test)
    # handle_message("https://youtube.com/watch?v=example", "12345")
    clear_memory()
    print("Memory cleared successfully.")