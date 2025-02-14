import os
import subprocess
import yt_dlp
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def process_youtube(url, chat_id, start_time=None, end_time=None):
    """Downloads and trims a YouTube video if start and end times are provided."""
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)  # Ensure output directory exists

    def download_video(url):
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        'socket_timeout': 10,
        'retries': 5,
        'logger': logger,  # Add logger to yt-dlp options
        'verbose': True,  # Enable verbose logging
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info_dict), info_dict.get('filesize', 0)
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        return None, 0

        # If trimming is required
        if start_time and end_time:
            trimmed_filename = f"{output_dir}/trimmed_{os.path.basename(video_filename)}"

            ffmpeg_cmd = [
                "ffmpeg", "-i", video_filename, "-ss", start_time, "-to", end_time,
                "-c", "copy", trimmed_filename, "-y"
            ]

            subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if os.path.exists(trimmed_filename):
                os.remove(video_filename)  # Delete original if trimming succeeded
                return trimmed_filename, os.path.getsize(trimmed_filename)
            else:
                logger.error("Trimming failed")
                return None

        return video_filename, os.path.getsize(video_filename)

    except Exception as e:
        logger.error(f"⚠️ Error processing YouTube video: {e}")
        return None


# Example of calling the function with correct arguments
def handle_message(url, chat_id, start_time=None, end_time=None):
    """Handles incoming messages and processes YouTube links."""
    try:
        result = process_youtube(url, chat_id, start_time, end_time)
        if result:
            logger.info(f"Video processed successfully: {result[0]}, Size: {result[1]} bytes")
        else:
            logger.error("Failed to process video.")
    except Exception as e:
        logger.error(f"⚠️ Error processing request: {e}")