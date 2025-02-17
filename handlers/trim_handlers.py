import os
import subprocess
import logging
from config import DOWNLOAD_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def trim_video(video_filename, start_time, end_time):
    """Trim video using FFmpeg."""
    trimmed_filename = os.path.join(DOWNLOAD_DIR, f"trimmed_{os.path.basename(video_filename)}")
    
    # FFmpeg command setup
    ffmpeg_cmd = [
        "ffmpeg", 
        "-y",  # Overwrite without asking
        "-ss", start_time,  # Start time
        "-i", video_filename,  # Input file
        "-to", end_time,  # End time
        "-c:v", "libx264",  # Video codec
        "-c:a", "aac",  # Audio codec
        "-strict", "experimental",  # For AAC codec support
        trimmed_filename
    ]
    
    try:
        # Run the FFmpeg command and capture both stdout and stderr
        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        
        # Check if the trimming process succeeded
        if os.path.exists(trimmed_filename):
            # Remove the original video file if trimming succeeded
            os.remove(video_filename)
            file_size = os.path.getsize(trimmed_filename) or 0
            logger.info(f"Video trimmed successfully: {trimmed_filename}, Size: {file_size} bytes")
            return trimmed_filename, file_size
        else:
            logger.error("Trimming failed. No output file found.")
            return None, 0
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e.stderr}")  # Log the stderr of the FFmpeg error
        return None, 0