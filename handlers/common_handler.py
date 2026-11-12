"""Generic yt-dlp handler for adult and other supported video websites.

This handler only downloads media that the source makes available to the
requesting account/session. It does not bypass DRM, paywalls, login controls,
or other access restrictions.
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

import yt_dlp

from config import DOWNLOAD_DIR, TELEGRAM_FILE_LIMIT, FFMPEG_PATH
from utils.sanitize import sanitize_filename
from utils.thumb_generator import generate_thumbnail
from utils.logger import setup_logging

logger = setup_logging(logging.DEBUG)

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".flv", ".ts",
}


def _downloaded_path(ydl: yt_dlp.YoutubeDL, info: dict) -> Path | None:
    """Resolve the actual final file path, including FFmpeg-merged output."""
    candidates: list[str] = []

    for item in info.get("requested_downloads") or []:
        if isinstance(item, dict):
            candidates.extend(
                value for value in (
                    item.get("filepath"),
                    item.get("_filename"),
                    item.get("filename"),
                ) if value
            )

    candidates.extend(
        value for value in (
            info.get("filepath"),
            info.get("_filename"),
            info.get("filename"),
        ) if value
    )

    try:
        prepared = ydl.prepare_filename(info)
        if prepared:
            candidates.append(prepared)
            stem = os.path.splitext(prepared)[0]
            candidates.extend(stem + ext for ext in (".mp4", ".mkv", ".webm"))
    except Exception:
        logger.debug("Could not resolve yt-dlp prepared filename", exc_info=True)

    seen: set[str] = set()
    for candidate in candidates:
        candidate = os.path.abspath(os.path.expanduser(str(candidate)))
        if candidate in seen:
            continue
        seen.add(candidate)
        path = Path(candidate)
        if path.is_file() and path.stat().st_size > 0:
            return path

    # Some extractors return a post-processed filepath only on the top-level
    # info dictionary. As a final safe fallback, find the newest media file
    # created in DOWNLOAD_DIR during this request.
    return None


def _safe_rename(path: Path, info: dict) -> Path:
    """Sanitize the extractor title while keeping its extension and ID."""
    safe_name = sanitize_filename(path.name)
    target = path.with_name(safe_name)
    if target == path:
        return path
    if target.exists():
        stem, suffix = target.stem, target.suffix
        counter = 2
        while target.exists():
            target = path.with_name(f"{stem}_{counter}{suffix}")
            counter += 1
    try:
        path.rename(target)
        return target
    except OSError:
        logger.warning("Could not sanitize downloaded filename: %s", path, exc_info=True)
        return path


def compress_video(input_file: str, output_file: str) -> str | None:
    """Compress a video with FFmpeg; return the output only on success."""
    command = [
        FFMPEG_PATH, "-hide_banner", "-loglevel", "error", "-y",
        "-i", input_file, "-c:v", "libx264", "-crf", "23",
        "-preset", "medium", "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", output_file,
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=1800, check=False
        )
        if result.returncode == 0 and os.path.isfile(output_file):
            logger.info("Video compressed: %s", output_file)
            return output_file
        logger.error("Video compression failed: %s", result.stderr[-1500:])
    except Exception:
        logger.exception("Video compression error")
    return None


def process_adult(url: str):
    """Download one video from any website with a yt-dlp extractor.

    Return contract: (file_path, file_size, thumbnail_path), matching bot.py.
    """
    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
    before = {
        str(path.resolve())
        for path in Path(DOWNLOAD_DIR).iterdir()
        if path.is_file()
    }

    ydl_opts = {
        # Prefer the best video+audio combination; fall back to a single-file
        # format on sites that do not expose separate streams.
        "format": "bestvideo*+bestaudio/best",
        "outtmpl": str(Path(DOWNLOAD_DIR) / "%(title).120B [%(id)s].%(ext)s"),
        "merge_output_format": "mp4",
        "ffmpeg_location": FFMPEG_PATH,
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 5,
        "fragment_retries": 5,
        "file_access_retries": 3,
        "extractor_retries": 3,
        "continuedl": True,
        "overwrites": False,
        "ignoreerrors": False,
        "concurrent_fragment_downloads": 2,
        "windowsfilenames": True,
        "trim_file_name": 180,
        "quiet": True,
        "no_warnings": True,
        "logger": logger,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    # Optional site-specific Netscape cookies can be supplied by the operator.
    # Never require or ask users to paste passwords/cookies into Telegram.
    cookie_file = os.getenv("ADULT_COOKIES_FILE", "").strip()
    if cookie_file and os.path.isfile(cookie_file) and os.path.getsize(cookie_file) > 0:
        ydl_opts["cookiefile"] = cookie_file
        logger.info("Using configured private cookie file for generic extractor")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not isinstance(info, dict):
                raise RuntimeError("The website did not return downloadable media metadata.")

            path = _downloaded_path(ydl, info)

        if path is None:
            # Use only files created by this invocation, so an old download
            # cannot accidentally be sent as the result of a failed request.
            new_files = [
                Path(item) for item in (
                    str(path.resolve())
                    for path in Path(DOWNLOAD_DIR).iterdir()
                    if path.is_file() and str(path.resolve()) not in before
                    and path.suffix.lower() in VIDEO_EXTENSIONS
                )
            ]
            if new_files:
                path = max(new_files, key=lambda item: item.stat().st_mtime)

        if path is None or not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(
                "yt-dlp finished without a usable video file. "
                "The site may be unsupported, private, or require authorized access."
            )

        path = _safe_rename(path, info)
        file_size = path.stat().st_size
        thumbnail_path = None
        try:
            thumbnail_path = generate_thumbnail(str(path))
        except Exception:
            logger.warning("Thumbnail generation failed for %s", path, exc_info=True)

        logger.info(
            "Generic video download completed: %s (%.2f MB)",
            path, file_size / (1024 * 1024),
        )

        if file_size > TELEGRAM_FILE_LIMIT:
            logger.warning(
                "Downloaded file exceeds Telegram upload limit: %.2f MB",
                file_size / (1024 * 1024),
            )

        return str(path), file_size, thumbnail_path

    except yt_dlp.utils.DownloadError as exc:
        logger.error("yt-dlp could not download %s: %s", url, exc)
    except (OSError, RuntimeError) as exc:
        logger.error("Generic video download failed for %s: %s", url, exc)
    except Exception:
        logger.exception("Unexpected generic video handler error for %s", url)

    return None, 0, None
