# handlers/threads_handler.py

import gc
import logging
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Tuple, Union

import yt_dlp

from config import DOWNLOAD_DIR
from utils.logger import setup_logging

logger = setup_logging(logging.DEBUG)

SUPPORTED_DOMAINS = {
    "threads.net",
    "www.threads.net",
    "threads.com",
    "www.threads.com",
}

MEDIA_EXTENSIONS = {
    ".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v",
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
}

Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)


def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return (
            result.scheme in {"http", "https"}
            and result.netloc.lower() in SUPPORTED_DOMAINS
        )
    except ValueError:
        return False


def _find_downloaded_files(info_dict) -> list[Path]:
    """Find final video/image files, including carousel entries."""
    files: list[Path] = []

    entries = info_dict.get("entries") if isinstance(info_dict, dict) else None
    items = list(entries) if entries else [info_dict]

    for entry in items:
        if not entry:
            continue

        candidates = []

        for item in entry.get("requested_downloads") or []:
            filepath = item.get("filepath")
            if filepath and Path(filepath).is_file():
                candidates.append(Path(filepath))

        for key in ("_filename", "filename"):
            filepath = entry.get(key)
            if filepath and Path(filepath).is_file():
                candidates.append(Path(filepath))

        chosen = next(
            (p for p in candidates if p.suffix.lower() in MEDIA_EXTENSIONS),
            None,
        )

        if chosen and chosen.is_file() and chosen not in files:
            files.append(chosen)

    return files


def process_threads(
    url: str,
) -> Tuple[Optional[Union[str, list]], int, Optional[str]]:
    """Download Threads videos, images, and carousel media."""
    url = url.split("#")[0]

    outtmpl = str(
        Path(DOWNLOAD_DIR) / "threads_%(id)s_%(title)s.%(ext)s"
    )

    ydl_opts = {
        "format": "bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": outtmpl,
        "noplaylist": False,
        "socket_timeout": 20,
        "retries": 5,
        "fragment_retries": 5,
        "quiet": True,
        "no_warnings": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.threads.net/",
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

        if not info_dict:
            return None, 0, "Failed to extract Threads media"

        media_paths = _find_downloaded_files(info_dict)

        if not media_paths:
            candidates = sorted(
                (
                    p for p in Path(DOWNLOAD_DIR).iterdir()
                    if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS
                ),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                media_paths = [candidates[0]]

        if not media_paths:
            return None, 0, "Threads download completed but no media file was found"

        total_size = sum(p.stat().st_size for p in media_paths)

        if len(media_paths) > 1:
            logger.info(
                "Threads carousel downloaded: %s files, %.2f MB total",
                len(media_paths),
                total_size / (1024 ** 2),
            )
            return [str(p) for p in media_paths], int(total_size), None

        media_path = media_paths[0]
        logger.info(
            "Threads media ready: %s (%.2f MB)",
            media_path,
            media_path.stat().st_size / (1024 ** 2),
        )
        return str(media_path), int(media_path.stat().st_size), None

    except yt_dlp.utils.DownloadError as e:
        logger.error("Threads download error: %s", e, exc_info=True)
        return None, 0, str(e)
    except Exception as e:
        logger.exception("Unexpected Threads error: %s", e)
        return None, 0, str(e)


def cleanup_media(media_path: str) -> None:
    try:
        path = Path(media_path)
        if path.exists():
            path.unlink()
            gc.collect()
    except Exception as e:
        logger.error("Failed to clean up %s: %s", media_path, e)
