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


async def extract_url_and_time(text):
    """Regex નો ઉપયોગ કરીને URL અને Start/End Time એક્સટ્રાક્ટ કરો"""
    match = re.match(r"(https?://[^\s]+)\s+(\d+)\s+(\d+)", text)
    if match:
        return match.groups()
    return None, None, None


async def trim_video(input_path, start_time, end_time):
    """FFmpeg Async Command Execution"""
    output_path = input_path.replace(".mp4", "_trimmed.mp4")
    cmd = ["ffmpeg", "-y", "-i", input_path, "-ss", str(start_time), "-to", str(end_time), "-c", "copy", output_path]

    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()

    return output_path if process.returncode == 0 else None

async def process_youtube_request(text):
    """Async Function to Process YouTube Download & Trim"""
    url, start, end = await extract_url_and_time(text)
    if not url:
        return "❌ **Invalid Format.** Please send: `<YouTube URL> <Start Time in sec> <End Time in sec>`"

    logging.info(f"Processing: {url}, Start: {start}s, End: {end}s")

    video_path = await process_youtube(url)
    if video_path:
        trimmed_path = await trim_video(video_path, start, end)
        return f"✅ **Trimmed Video Ready:** `{trimmed_path}`" if trimmed_path else "❌ **Trimming Failed.**"
    return "❌ **Download Failed.**"