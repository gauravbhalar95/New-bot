import os
import sys
import asyncio
import yt_dlp
import logging
from utils.sanitize import sanitize_filename
from config import YOUTUBE_FILE, DOWNLOAD_DIR
from utils.logger import setup_logging

logger = setup_logging(logging.DEBUG)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

async def run_ffmpeg(video_filename, start_time, end_time, trimmed_filename):
    def time_to_seconds(time_str):
        h, m, s = map(int, time_str.split(':'))
        return h * 3600 + m * 60 + s

    duration = time_to_seconds(end_time) - time_to_seconds(start_time)
    if duration <= 0:
        logger.error("❌ Invalid time range")
        return None

    ffmpeg_cmd = ['ffmpeg', '-y', '-i', video_filename, '-ss', str(time_to_seconds(start_time)),
                  '-t', str(duration), '-c:v', 'copy', '-c:a', 'copy', trimmed_filename]
    
    process = await asyncio.create_subprocess_exec(*ffmpeg_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()
    
    return trimmed_filename if process.returncode == 0 else None

async def download_and_trim_video(youtube_url, start_time, end_time):
    ydl_opts = {
        'format': 'bv*+ba/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        'merge_output_format': 'mp4',
        'retries': 5,
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await asyncio.to_thread(ydl.extract_info, youtube_url, True)
            if not info_dict:
                logger.error("❌ Download failed")
                return None

            video_filename = ydl.prepare_filename(info_dict).replace('.webm', '.mp4')
            trimmed_filename = video_filename.replace('.mp4', '_trimmed.mp4')
            return await run_ffmpeg(video_filename, start_time, end_time, trimmed_filename)

    except Exception as e:
        logger.error(f"⚠️ Error: {e}")
        return None

async def main():
    if len(sys.argv) != 4:
        print("Usage: <YouTube_URL> <Start_Time> <End_Time>")
        sys.exit(1)

    trimmed_video = await download_and_trim_video(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f"✅ Trimmed Video Saved: {trimmed_video}" if trimmed_video else "❌ Failed to process the video.")

if __name__ == "__main__":
    asyncio.run(main())