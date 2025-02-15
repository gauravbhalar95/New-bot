import os
import subprocess
import yt_dlp
import logging
from config import YOUTUBE_FILE, DOWNLOAD_DIR

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def sanitize_filename(name):
    """Sanitize the filename by removing or replacing invalid characters."""
    return "".join(c for c in name if c.isalnum() or c in (' ', '.', '_')).rstrip()

def process_youtube(url):
    """Download video using yt-dlp."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
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
            if not info_dict:
                logger.error("No info_dict returned. Download failed.")
                return None, 0
            file_size = info_dict.get('filesize', 0) or 0
            return ydl.prepare_filename(info_dict), file_size
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        return None, 0

def extract_audio(url):
    """Download and extract audio from a YouTube video using yt-dlp."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    audio_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'logger': logger,
        'verbose': True,
    }
    try:
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            if not info_dict:
                logger.error("No info_dict returned. Audio download failed.")
                return None, 0
            audio_filename = ydl.prepare_filename(info_dict).replace('.webm', '.mp3').replace('.m4a', '.mp3')
            file_size = os.path.getsize(audio_filename) if os.path.exists(audio_filename) else 0
            return audio_filename, file_size
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        return None, 0

def trim_video(video_filename, start_time, end_time):
    """Trim video using FFmpeg."""
    trimmed_filename = os.path.join(DOWNLOAD_DIR, f"trimmed_{os.path.basename(video_filename)}")
    ffmpeg_cmd = [
        "ffmpeg", 
        "-y",  # Overwrite without asking
        "-ss", start_time,  # Start time
        "-i", video_filename,  # Input file
        "-to", end_time,  # End time
        "-c:v", "libx264",  # Video codec
        "-c:a", "aac",  # Audio codec
        "-strict", "experimental",
        trimmed_filename
    ]
    try:
        subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if os.path.exists(trimmed_filename):
            os.remove(video_filename)  # Delete original if trimming succeeded
            file_size = os.path.getsize(trimmed_filename) or 0
            return trimmed_filename, file_size
        else:
            logger.error("Trimming failed")
            return None, 0
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e}")
        return None, 0

def process_youtube_full(url, start_time=None, end_time=None, audio_only=False):
    """Download and optionally trim a YouTube video or extract audio."""
    if audio_only:
        return extract_audio(url)
    video_filename, file_size = process_youtube(url)
    file_size = file_size or 0
    if not video_filename:
        return None, 0
    if start_time and end_time:
        return trim_video(video_filename, start_time, end_time)
    return video_filename, file_size

def handle_message(url, start_time=None, end_time=None, audio_only=False):
    """Handles incoming messages and processes YouTube links."""
    try:
        result = process_youtube_full(url, start_time, end_time, audio_only)
        if result and result[0]:
            if os.path.exists(result[0]):
                logger.info(f"File processed successfully: {result[0]}, Size: {result[1]} bytes")
            else:
                logger.error("File path does not exist.")
        else:
            logger.error("Failed to process file.")
    except Exception as e:
        logger.error(f"⚠️ Error processing request: {e}")

if __name__ == "__main__":
    logger.info("Starting YouTube processing...")
    # Example usage (uncomment to test)
    # handle_message("https://youtube.com/watch?v=example", "00:00:10", "00:01:00")
    # handle_message("https://youtube.com/watch?v=example", audio_only=True)
    logger.info("Process complete.")