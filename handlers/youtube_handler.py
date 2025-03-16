import os
import asyncio
import yt_dlp
import logging
from pathlib import Path
from utils.sanitize import sanitize_filename
from config import YOUTUBE_FILE, DOWNLOAD_DIR
from utils.logger import setup_logging
from utils.thumb_generator import *

# Initialize logger
logger = setup_logging(logging.DEBUG)

# Ensure download directory exists
Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)

async def process_youtube(url: str) -> tuple[str | None, int, str | None]:
    """Download video using yt-dlp asynchronously."""
    ydl_opts = {
        'format': 'bv+ba/b',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'cookiefile': YOUTUBE_FILE if Path(YOUTUBE_FILE).exists() else None,
        'socket_timeout': 10,
        'retries': 5,
        'logger': logger,
        'verbose': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await asyncio.to_thread(ydl.extract_info, url, True)
            if not info_dict:
                logger.error("❌ No info_dict returned. Download failed.")
                return None, 0, None 

            file_path = ydl.prepare_filename(info_dict)
            file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
            return file_path, file_size, None
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ Download error: {e}")
    except Exception as e:
        logger.error(f"⚠️ Unexpected error downloading video: {e}")
    return None, 0, None

async def extract_audio(url: str) -> tuple[str | None, int]:
    """Download and extract audio from a YouTube video asynchronously."""
    audio_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'cookiefile': YOUTUBE_FILE if Path(YOUTUBE_FILE).exists() else None,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'logger': logger,
        'verbose': True,
    }
    try:
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            info_dict = await asyncio.to_thread(ydl.extract_info, url, True)
            if not info_dict:
                logger.error("❌ No info_dict returned. Audio download failed.")
                return None, 0

            audio_filename = Path(ydl.prepare_filename(info_dict)).with_suffix('.mp3')
            file_size = audio_filename.stat().st_size if audio_filename.exists() else 0
            return str(audio_filename), file_size
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ Audio download error: {e}")
    except Exception as e:
        logger.error(f"⚠️ Unexpected error extracting audio: {e}")
    return None, 0

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

        audio_file = Path(audio_path)
        return audio_file.exists() and audio_file.stat().st_size > 0
    except FileNotFoundError:
        logger.error("❌ FFmpeg not found. Ensure FFmpeg is installed and in PATH.")
    except Exception as e:
        logger.error(f"⚠️ FFmpeg error: {e}")
    return False

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
    except FileNotFoundError:
        logger.error("❌ FFprobe not found. Ensure FFmpeg is installed and in PATH.")
    except Exception as e:
        logger.error(f"⚠️ FFprobe error: {e}")
    return 0

if __name__ == "__main__":
    asyncio.run(main())