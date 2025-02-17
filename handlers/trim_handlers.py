import os
import logging
from config import DOWNLOAD_DIR
import yt_dlp

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

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