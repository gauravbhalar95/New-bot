# handlers/instagram_handler.py

import gc
import logging
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Tuple, Union

import yt_dlp

from config import DOWNLOAD_DIR, COOKIES_FILE
from utils.logger import setup_logging


logger = setup_logging(logging.DEBUG)

logger.add(
    "instagram_handler.log",
    rotation="10 MB",
    level="DEBUG"
)

SUPPORTED_DOMAINS = ["instagram.com"]

Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)


def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return (
            result.scheme in ["http", "https"]
            and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
        )
    except ValueError:
        return False


def is_instagram_video(url: str) -> bool:
    return any(x in url for x in ["/reel/", "/tv/", "/video/"])


def download_progress_hook(d: dict) -> None:
    status = d.get("status")

    if status == "downloading":
        logger.info(
            "Downloading... %s at %s, ETA: %s",
            d.get("_percent_str", "0%"),
            d.get("_speed_str", "N/A"),
            d.get("_eta_str", "N/A"),
        )
    elif status == "finished":
        logger.info("✅ Download finished: %s", d.get("filename"))


def _find_downloaded_files(info_dict) -> list[Path]:
    """Find all final media files produced by yt-dlp, including carousels."""
    files = []

    entries = info_dict.get("entries") if isinstance(info_dict, dict) else None
    items = list(entries) if entries else [info_dict]

    for entry in items:
        if not entry:
            continue

        requested = entry.get("requested_downloads") or []
        candidates = []

        for item in requested:
            filepath = item.get("filepath")
            if filepath and Path(filepath).is_file():
                candidates.append(Path(filepath))

        for key in ("_filename", "filename"):
            filepath = entry.get(key)
            if filepath and Path(filepath).is_file():
                candidates.append(Path(filepath))

        # Prefer the merged MP4 over source streams.
        mp4 = next(
            (p for p in candidates if p.suffix.lower() == ".mp4"),
            None,
        )
        chosen = mp4 or (candidates[0] if candidates else None)

        if chosen and chosen.is_file() and chosen not in files:
            files.append(chosen)

    return files


def process_instagram(
    url: str
) -> Tuple[Optional[Union[str, list]], int, Optional[str]]:

    url = url.split("#")[0]

    cookie_path = Path(COOKIES_FILE)

    if not cookie_path.exists() or cookie_path.stat().st_size == 0:
        logger.error("❌ Instagram cookies file is missing or empty!")
        return None, 0, "Instagram cookies file is missing or empty"

    outtmpl = str(
        Path(DOWNLOAD_DIR) / "%(uploader)s - %(title)s.%(ext)s"
    )

    ydl_opts = {
        # Download both streams when Instagram exposes separate video/audio.
        # FFmpeg only muxes them; it does not re-encode the video here.
        "format": "bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": outtmpl,
        "socket_timeout": 20,
        "retries": 5,
        "fragment_retries": 5,
        "progress_hooks": [download_progress_hook],
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
            info_dict = ydl.extract_info(url, download=True)

        if not info_dict:
            return None, 0, "❌ Failed to extract info"

        video_paths = _find_downloaded_files(info_dict)

        # Single-item fallback: find the newest media file if yt-dlp did not
        # expose a final filepath.
        if not video_paths:
            media_extensions = {
                ".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"
            }
            candidates = sorted(
                (
                    p for p in Path(DOWNLOAD_DIR).iterdir()
                    if p.is_file() and p.suffix.lower() in media_extensions
                ),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                video_paths = [candidates[0]]

        if not video_paths:
            logger.error("❌ Instagram download completed but no media file was found.")
            return (
                None,
                0,
                "❌ Download completed, but the media file could not be found.",
            )

        total_size = sum(p.stat().st_size for p in video_paths)

        if len(video_paths) > 1:
            logger.info(
                "✅ Instagram carousel downloaded: %s media files, %.2f MB total",
                len(video_paths),
                total_size / (1024 ** 2),
            )
            return [str(p) for p in video_paths], int(total_size), None

        video_path = video_paths[0]
        logger.info(
            "✅ Final Instagram video ready: %s (%.2f MB)",
            video_path,
            video_path.stat().st_size / (1024 ** 2),
        )

        if video_path.suffix.lower() == ".mp4":
            logger.info(
                "✅ MP4 contains merged video/audio when separate audio was available."
            )

        return str(video_path), int(video_path.stat().st_size), None

    except yt_dlp.utils.DownloadError as e:
        logger.error("❌ Instagram download error: %s", e, exc_info=True)
        return None, 0, str(e)

    except Exception as e:
        logger.exception("⚠️ Unexpected Instagram error: %s", e)
        return None, 0, str(e)


def cleanup_video(video_path: str) -> None:
    video_file = Path(video_path)

    try:
        if video_file.exists():
            video_file.unlink()
            gc.collect()
            logger.info("🧹 Cleaned up %s", video_path)
    except Exception as e:
        logger.error("❌ Failed to clean up %s: %s", video_path, e)
