import os
import asyncio
import yt_dlp
import logging
from utils.sanitize import sanitize_filename
from config import YOUTUBE_FILE, DOWNLOAD_DIR
from utils.logger import setup_logging
import sys

# Initialize logger
logger = setup_logging(logging.DEBUG)

async def process_youtube(url):
    """Download video using yt-dlp asynchronously."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    ydl_opts = {
        'format': 'bv+ba/b',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        'socket_timeout': 10,
        'retries': 5,
        'logger': logger,
        'verbose': True,
    }
    try:
        loop = asyncio.get_running_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await loop.run_in_executor(None, ydl.extract_info, url, True)
            if not info_dict:
                logger.error("❌ No info_dict returned. Download failed.")
                return None, 0, "❌ No video information found."

            # Handle unavailable video error directly
            if 'entries' in info_dict and not info_dict['entries']:
                logger.error("❌ Video unavailable or restricted.")
                return None, 0, "❌ Video unavailable or restricted."

            file_path = ydl.prepare_filename(info_dict)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            return file_path, file_size, None
    except yt_dlp.utils.ExtractorError as e:
        logger.error(f"❌ Extractor Error: {e}")
        return None, 0, "❌ Video may be private, deleted, or region-restricted."
    except Exception as e:
        logger.error(f"⚠️ Error downloading video: {e}")
        return None, 0, str(e)

async def extract_audio(url):
    """Download and extract audio from a YouTube video asynchronously."""
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
        loop = asyncio.get_running_loop()
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            info_dict = await loop.run_in_executor(None, ydl.extract_info, url, True)
            if not info_dict:
                logger.error("❌ No info_dict returned. Audio download failed.")
                return None, 0

            audio_filename = ydl.prepare_filename(info_dict).replace('.webm', '.mp3').replace('.m4a', '.mp3')
            file_size = os.path.getsize(audio_filename) if os.path.exists(audio_filename) else 0
            return audio_filename, file_size
    except yt_dlp.utils.ExtractorError as e:
        logger.error(f"❌ Extractor Error: {e}")
        return None, 0
    except Exception as e:
        logger.error(f"⚠️ Error extracting audio: {e}")
        return None, 0


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