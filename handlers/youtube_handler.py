import os
import yt_dlp
import logging

from utils.sanitize import sanitize_filename
from config import YOUTUBE_FILE, DOWNLOAD_DIR
from utils.logger import setup_logging


# Initialize logger
logger = setup_logging(logging.DEBUG)


def process_youtube(url):
    """Download video using yt-dlp synchronously."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    ydl_opts = {
        "format": "bv+ba/b",
        "outtmpl": f"{DOWNLOAD_DIR}/{sanitize_filename('%(title)s')}.%(ext)s",
        "cookiefile": YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        "socket_timeout": 10,
        "retries": 5,
        "logger": logger,
        "verbose": True,
        "merge_output_format": "mp4",
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

            if not info_dict:
                logger.error("❌ No info_dict returned. Download failed.")
                return None, 0, "❌ No video information found."

            if "entries" in info_dict and not info_dict["entries"]:
                logger.error("❌ Video unavailable or restricted.")
                return None, 0, "❌ Video unavailable or restricted."

            file_path = ydl.prepare_filename(info_dict)

            mp4_path = os.path.splitext(file_path)[0] + ".mp4"

            if os.path.exists(mp4_path):
                file_path = mp4_path

            file_size = (
                os.path.getsize(file_path)
                if os.path.exists(file_path)
                else 0
            )

            return file_path, file_size, None

    except yt_dlp.utils.ExtractorError as e:
        logger.error(f"❌ Extractor Error: {e}")
        return (
            None,
            0,
            "❌ Video may be private, deleted, or region-restricted."
        )

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ Download Error: {e}")
        return None, 0, str(e)

    except Exception as e:
        logger.error(
            f"⚠️ Error downloading video: {e}",
            exc_info=True
        )
        return None, 0, str(e)


def extract_audio_ffmpeg(url):
    """Download and extract audio from a YouTube video synchronously."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    audio_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{DOWNLOAD_DIR}/{sanitize_filename('%(title)s')}.%(ext)s",
        "cookiefile": YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }],
        "logger": logger,
        "verbose": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

            if not info_dict:
                logger.error(
                    "❌ No info_dict returned. Audio download failed."
                )
                return None, 0

            audio_filename = ydl.prepare_filename(info_dict)

            audio_filename = os.path.splitext(audio_filename)[0] + ".mp3"

            file_size = (
                os.path.getsize(audio_filename)
                if os.path.exists(audio_filename)
                else 0
            )

            return audio_filename, file_size

    except yt_dlp.utils.ExtractorError as e:
        logger.error(f"❌ Extractor Error: {e}")
        return None, 0

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ Download Error: {e}")
        return None, 0

    except Exception as e:
        logger.error(
            f"⚠️ Error extracting audio: {e}",
            exc_info=True
        )
        return None, 0