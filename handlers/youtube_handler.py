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
    
    # Download options for yt-dlp
    ydl_opts = {
        "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
        "format": "bestvideo+bestaudio/best",
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_filename = ydl.prepare_filename(info)

        if not os.path.exists(video_filename):
            return None  # Download failed

        # If trimming is required
        if start_time and end_time:
            trimmed_filename = f"{output_dir}/trimmed_{os.path.basename(video_filename)}"

            # Run ffmpeg to trim the video
            ffmpeg_cmd = [
                "ffmpeg", "-i", video_filename, "-ss", start_time, "-to", end_time,
                "-c", "copy", trimmed_filename, "-y"
            ]
            
            subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if os.path.exists(trimmed_filename):
                os.remove(video_filename)  # Delete original if trimming succeeded
                return trimmed_filename, os.path.getsize(trimmed_filename)
            else:
                return None  # Trimming failed

        return video_filename, os.path.getsize(video_filename)  # Return original file

    except Exception as e:
        logger.error(f"⚠️ Error processing YouTube video: {e}")
        return None