import os
import sys
import asyncio
import yt_dlp
import logging
from utils.sanitize import sanitize_filename
from config import YOUTUBE_FILE, DOWNLOAD_DIR
from utils.logger import setup_logging

# Logger Initialization
logger = setup_logging(logging.DEBUG)

# Ensure the download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

async def run_ffmpeg(video_filename, start_time, end_time, trimmed_filename):
    """Run FFmpeg asynchronously to trim the video."""
    # Convert start_time and end_time to seconds
    def time_to_seconds(time_str):
        h, m, s = map(int, time_str.split(':'))
        return h * 3600 + m * 60 + s

    start_seconds = time_to_seconds(start_time)
    end_seconds = time_to_seconds(end_time)
    duration = end_seconds - start_seconds

    if duration <= 0:
        logger.error("❌ Invalid time range: end_time must be greater than start_time.")
        return None

    ffmpeg_cmd = [
        'ffmpeg', '-y', '-i', video_filename,
        '-ss', str(start_seconds), '-t', str(duration),
        '-c:v', 'copy', '-c:a', 'copy', trimmed_filename
    ]

    logger.info(f"Running FFmpeg command: {' '.join(ffmpeg_cmd)}")

    process = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        logger.error(f"⚠️ FFmpeg Error: {stderr.decode().strip()}")
        return None

    return trimmed_filename

async def download_and_trim_video(youtube_url, start_time, end_time):
    """Download a YouTube video and trim it using FFmpeg asynchronously."""

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
        loop = asyncio.get_running_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await loop.run_in_executor(None, ydl.extract_info, youtube_url, True)
            if not info_dict:
                logger.error("❌ Download failed: No info_dict returned.")
                return None

            video_filename = ydl.prepare_filename(info_dict)
            if not video_filename.endswith('.mp4'):
                video_filename = video_filename.rsplit('.', 1)[0] + '.mp4'

            logger.info(f"✅ Downloaded Video: {video_filename}")

            trimmed_filename = video_filename.replace('.mp4', '_trimmed.mp4')

            # Trim the video using FFmpeg
            trimmed_result = await run_ffmpeg(video_filename, start_time, end_time, trimmed_filename)

            if trimmed_result:
                os.remove(video_filename)  # Cleanup original file
                logger.info(f"✅ Trimmed video saved: {trimmed_result}")
                return trimmed_result
            else:
                logger.error("⚠️ Error trimming video.")
                return None

    except Exception as e:
        logger.error(f"⚠️ Error downloading and trimming video: {e}")
        return None

async def main():
    if len(sys.argv) != 4:
        print("Usage:<YouTube_URL> <Start_Time> <End_Time>")
        sys.exit(1)

    youtube_url = sys.argv[1]
    start_time = sys.argv[2]  # Format: HH:MM:SS
    end_time = sys.argv[3]    # Format: HH:MM:SS

    trimmed_video = await download_and_trim_video(youtube_url, start_time, end_time)
    if trimmed_video:
        print(f"✅ Trimmed Video Saved: {trimmed_video}")
    else:
        print("❌ Failed to process the video.")

if __name__ == "__main__":
    asyncio.run(main())