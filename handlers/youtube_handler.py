import os
import asyncio
import yt_dlp
import logging
from utils.sanitize import sanitize_filename
from config import DOWNLOAD_DIR, YOUTUBE_FILE
from utils.logger import setup_logging

logger = setup_logging(logging.DEBUG)


async def process_youtube(url: str):
    """
    Download YouTube video / Shorts safely using yt-dlp.
    Returns: (file_path, file_size, error_message)
    """

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    ydl_opts = {
        # ✅ Shorts-safe + normal video safe
        "format": (
            "bv*[ext=mp4]+ba[ext=m4a]/"
            "bv*+ba/b/"
            "best"
        ),
        "merge_output_format": "mp4",

        "outtmpl": f"{DOWNLOAD_DIR}/{sanitize_filename('%(title)s')}.%(ext)s",

        # cookies optional
        "cookiefile": YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,

        "retries": 5,
        "socket_timeout": 15,

        # stability
        "quiet": True,
        "no_warnings": True,

        # important for Shorts / SABR
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
                "skip": ["dash"],
            }
        },

        "logger": logger,
    }

    try:
        loop = asyncio.get_running_loop()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(url, download=True)
            )

            if not info:
                return None, 0, "❌ Failed to extract video info"

            # Playlist safety
            if "entries" in info:
                info = info["entries"][0]

            file_path = ydl.prepare_filename(info)

            # If merged to mp4, yt-dlp may rename it
            if not os.path.exists(file_path):
                base, _ = os.path.splitext(file_path)
                mp4_path = base + ".mp4"
                if os.path.exists(mp4_path):
                    file_path = mp4_path

            if not os.path.exists(file_path):
                return None, 0, "❌ Download completed but file not found"

            file_size = os.path.getsize(file_path)

            logger.info(f"✅ YouTube download finished: {file_path}")
            return file_path, file_size, None

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"YouTube DownloadError: {e}")
        return None, 0, "❌ YouTube format unavailable or restricted"

    except Exception as e:
        logger.exception("YouTube handler crashed")
        return None, 0, str(e)