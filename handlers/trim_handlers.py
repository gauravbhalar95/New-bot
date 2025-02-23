import os
import logging
from config import DOWNLOAD_DIR
from utils.sanitize import sanitize_filename  # Sanitization utility
import yt_dlp
from utils.logger import setup_logging


# Initialize logger
logger = setup_logging(logging.DEBUG) #Example of setting to debug level.


def download_and_trim_video(youtube_url, start_time, end_time):
    """Download and trim video from YouTube using yt-dlp with postprocessor_args."""
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),  # Save video in DOWNLOAD_DIR
        'postprocessor_args': ['-ss', start_time, '-to', end_time],  # FFmpeg trimming arguments
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',  # Use FFmpeg for post-processing
            'preferedformat': 'mp4',  # Convert to mp4
        }]
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(youtube_url, download=True)
            video_filename = os.path.join(DOWNLOAD_DIR, f"{result['id']}.mp4")
            logger.info(f"Trimmed video downloaded: {video_filename}")
            return video_filename
    except Exception as e:
        logger.error(f"Error downloading and trimming video: {e}")
        return None

def main(youtube_url, start_time, end_time):
    video_filename = download_and_trim_video(youtube_url, start_time, end_time)
    if video_filename:
        logger.info(f"Trimmed video saved at: {video_filename}")
    else:
        logger.error("Video download and trimming failed.")

if __name__ == "__main__":
    youtube_url = "https://www.youtube.com/live/oh6uMYY_9-o?si=C2xsVhPKOIxrESlp"
    start_time = "00:01:00"  # Example start time
    end_time = "00:05:00"    # Example end time
    main(youtube_url, start_time, end_time)

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