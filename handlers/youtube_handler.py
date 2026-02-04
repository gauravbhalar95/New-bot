import os
import asyncio
import yt_dlp
import logging

from utils.sanitize import sanitize_filename
from config import YOUTUBE_FILE, DOWNLOAD_DIR
from utils.logger import setup_logging

# Telegram bot upload limit (safe side)
MAX_TG_SIZE = 50 * 1024 * 1024  # 50MB

logger = setup_logging(logging.INFO)


# =========================
# 🎥 YOUTUBE VIDEO DOWNLOAD
# =========================
async def process_youtube(url: str):
    """
    Download YouTube video as MP4 with audio.
    Returns: (file_path, file_size, error_message)
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    ydl_opts = {
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]",
        "merge_output_format": "mp4",
        "outtmpl": f"{DOWNLOAD_DIR}/{sanitize_filename('%(title)s')}.%(ext)s",
        "cookiefile": YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        "retries": 5,
        "socket_timeout": 10,
        "quiet": True,
        "no_warnings": True,
        "logger": logger,
    }

    try:
        loop = asyncio.get_running_loop()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(url, download=True)
            )

        if not info:
            return None, 0, "❌ Failed to fetch video info."

        file_path = info.get("_filename")
        if not file_path or not os.path.exists(file_path):
            return None, 0, "❌ Video file not found after download."

        file_size = os.path.getsize(file_path)
        logger.info(f"✅ YouTube downloaded: {file_path} ({file_size / 1024 / 1024:.2f} MB)")

        return file_path, file_size, None

    except yt_dlp.utils.ExtractorError:
        return None, 0, "❌ Video is private, deleted, or restricted."
    except Exception as e:
        logger.exception("YouTube download error")
        return None, 0, str(e)


# =========================
# 🎵 YOUTUBE AUDIO (MP3)
# =========================
async def extract_audio_ffmpeg(url: str):
    """
    Download YouTube audio and convert to MP3.
    Returns: (file_path, file_size, error_message)
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{DOWNLOAD_DIR}/{sanitize_filename('%(title)s')}.%(ext)s",
        "cookiefile": YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }
        ],
        "quiet": True,
        "no_warnings": True,
        "logger": logger,
    }

    try:
        loop = asyncio.get_running_loop()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(url, download=True)
            )

        if not info:
            return None, 0, "❌ Failed to extract audio."

        base = ydl.prepare_filename(info)
        audio_path = os.path.splitext(base)[0] + ".mp3"

        if not os.path.exists(audio_path):
            return None, 0, "❌ MP3 file not found."

        size = os.path.getsize(audio_path)
        logger.info(f"✅ Audio extracted: {audio_path}")

        return audio_path, size, None

    except yt_dlp.utils.ExtractorError:
        return None, 0, "❌ Audio extraction failed."
    except Exception as e:
        logger.exception("Audio extraction error")
        return None, 0, str(e)


# =========================
# 📤 TELEGRAM SEND HELPER
# =========================
async def send_video_safely(bot, chat_id, file_path, file_size, upload_fallback_func):
    """
    Sends video to Telegram if <= 50MB
    Otherwise uploads to MEGA / Dropbox and sends link
    """
    if file_size <= MAX_TG_SIZE:
        video = open(file_path, "rb")
        await bot.send_video(chat_id, video)
        video.close()
    else:
        link = await upload_fallback_func(file_path)
        await bot.send_message(
            chat_id,
            f"📦 Video too large for Telegram\n🔗 Download link:\n{link}"
        )