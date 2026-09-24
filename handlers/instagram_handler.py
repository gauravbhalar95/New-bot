# handlers/instagram_handler.py

import gc
import logging
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Tuple

import yt_dlp

from config import DOWNLOAD_DIR, COOKIES_FILE
from utils.logger import setup_logging


logger = setup_logging(logging.DEBUG)

logger.add(
    "instagram_handler.log",
    rotation="10 MB",
    level="DEBUG"
)


SUPPORTED_DOMAINS = [
    "instagram.com"
]


Path(DOWNLOAD_DIR).mkdir(
    parents=True,
    exist_ok=True
)


def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return (
            result.scheme in ["http", "https"]
            and any(
                domain in result.netloc
                for domain in SUPPORTED_DOMAINS
            )
        )
    except ValueError:
        return False


def is_instagram_video(url: str) -> bool:
    return any(
        x in url
        for x in [
            "/reel/",
            "/tv/",
            "/video/"
        ]
    )


def download_progress_hook(d: dict) -> None:
    status = d.get("status")

    if status == "downloading":
        percent = d.get("_percent_str", "0%")
        speed = d.get("_speed_str", "N/A")
        eta = d.get("_eta_str", "N/A")

        logger.info(
            f"Downloading... "
            f"{percent} at {speed}, ETA: {eta}"
        )

    elif status == "finished":
        logger.info(
            f"✅ Download finished: "
            f"{d.get('filename')}"
        )


def process_instagram(
    url: str
) -> Tuple[Optional[str], int, Optional[str]]:

    url = url.split("#")[0]

    cookie_path = Path(COOKIES_FILE)

    if (
        not cookie_path.exists()
        or cookie_path.stat().st_size == 0
    ):
        logger.error(
            "❌ Instagram cookies file is missing or empty!"
        )
        return (
            None,
            0,
            "Instagram cookies file is missing or empty"
        )

    outtmpl = str(
        Path(DOWNLOAD_DIR)
        / "%(uploader)s - %(title)s.%(ext)s"
    )

    ydl_opts = {
        # IMPORTANT:
        # "best" can select a video-only stream. Explicitly request the
        # best video AND best audio, then let FFmpeg MERGE them. This is
        # a mux/remux operation when the codecs are already compatible;
        # it does not re-encode the video just to send it to Telegram.
        "format": "bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",

        "outtmpl": outtmpl,

        "socket_timeout": 20,
        "retries": 5,
        "fragment_retries": 5,

        "progress_hooks": [
            download_progress_hook
        ],

        "cookiefile": str(cookie_path),

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; "
                "rv:123.0 Gecko/20100101 Firefox/123.0"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.instagram.com/",
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(
                url,
                download=True
            )

        if not info_dict:
            return (
                None,
                0,
                "❌ Failed to extract info"
            )

        # Prefer the actual final file reported by yt-dlp.
        video_path = None

        requested_downloads = info_dict.get("requested_downloads") or []

        for item in requested_downloads:
            filepath = item.get("filepath")
            if filepath and Path(filepath).is_file():
                candidate = Path(filepath)

                # Prefer the merged/final file over an individual stream.
                if candidate.suffix.lower() == ".mp4":
                    video_path = candidate
                    break

                if video_path is None:
                    video_path = candidate

        if video_path is None:
            for key in ("_filename", "filename"):
                filepath = info_dict.get(key)
                if filepath and Path(filepath).is_file():
                    video_path = Path(filepath)
                    break

        # Final fallback: choose the newest media file created by the
        # download. Prefer MP4 because that is normally the merged result.
        if video_path is None:
            media_extensions = {
                ".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"
            }

            candidates = sorted(
                (
                    p for p in Path(DOWNLOAD_DIR).iterdir()
                    if p.is_file()
                    and p.suffix.lower() in media_extensions
                ),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            if candidates:
                video_path = candidates[0]

        if video_path is None or not video_path.is_file():
            logger.error(
                "❌ Download completed but the final media file "
                "could not be located."
            )
            return (
                None,
                0,
                "❌ Download completed, but the video file could not be found."
            )

        file_size = video_path.stat().st_size

        logger.info(
            f"✅ Final Instagram video ready: {video_path} "
            f"({file_size / (1024 ** 2):.2f} MB)"
        )

        if video_path.suffix.lower() == ".mp4":
            logger.info(
                "✅ Final file is MP4 with video+audio merged. "
                "Sending original file without re-encoding."
            )

        return (
            str(video_path),
            int(file_size),
            None
        )

    except yt_dlp.utils.DownloadError as e:
        logger.error(
            f"❌ Instagram download error: {e}",
            exc_info=True
        )
        return (
            None,
            0,
            str(e)
        )

    except Exception as e:
        logger.exception(
            "⚠️ Unexpected error downloading "
            f"Instagram video: {e}"
        )
        return (
            None,
            0,
            str(e)
        )


def cleanup_video(
    video_path: str
) -> None:

    video_file = Path(video_path)

    try:
        if video_file.exists():
            video_file.unlink()
            gc.collect()
            logger.info(
                f"🧹 Cleaned up {video_path}"
            )

    except Exception as e:
        logger.error(
            f"❌ Failed to clean up "
            f"{video_path}: {e}"
        )
