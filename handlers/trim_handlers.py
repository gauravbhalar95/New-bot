import os
import subprocess
import logging
from config import DOWNLOAD_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

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