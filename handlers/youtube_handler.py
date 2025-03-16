import os
import asyncio
import yt_dlp
import logging
from utils.sanitize import sanitize_filename
from config import YOUTUBE_FILE, DOWNLOAD_DIR
from utils.logger import setup_logging

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
                return None, 0, None 

            file_path = ydl.prepare_filename(info_dict)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            return file_path, file_size, None
    except Exception as e:
        logger.error(f"⚠️ Error downloading video: {e}")
        return None, 0, None

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
    except Exception as e:
        logger.error(f"⚠️ Error extracting audio: {e}")
        return None, 0

# FFmpeg-based audio extraction
async def extract_audio_ffmpeg(video_path: str, audio_path: str) -> bool:
    """Converts video to audio using FFmpeg."""
    try:
        cmd = [
            "ffmpeg", "-i", video_path,
            "-vn", "-acodec", "libmp3lame",
            "-b:a", "192k",
            "-y", audio_path
        ]
        process = await asyncio.create_subprocess_exec(*cmd)
        await process.communicate()
        return os.path.exists(audio_path) and os.path.getsize(audio_path) > 0
    except Exception as e:
        logger.error(f"⚠️ FFmpeg error: {e}")
        return False

# Video duration retrieval
async def get_video_duration(video_path: str) -> float:
    """Retrieve video duration using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-i", video_path,
            "-show_entries", "format=duration",
            "-v", "quiet", "-of", "csv=p=0"
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        return float(stdout.strip()) if stdout else 0
    except Exception as e:
        logger.error(f"⚠️ FFprobe error: {e}")
        return 0