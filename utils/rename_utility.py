"""Utilities for giving downloaded media files creator-based filenames."""
from __future__ import annotations

import os
import re
import unicodedata
from urllib.parse import urlparse


def _safe_filename_part(value: str, fallback: str = "download") -> str:
    """Return a short, filesystem-safe filename component."""
    value = unicodedata.normalize("NFKC", str(value or ""))
    value = re.sub(r"[\\/\\:*?\"<>|\x00-\x1f]", "", value)
    value = re.sub(r"\s+", "_", value.strip())
    value = re.sub(r"[^\w.\-]", "", value, flags=re.UNICODE)
    value = value.strip(" ._-")
    return (value[:80] or fallback)


def username_from_url(source_url: str | None) -> str | None:
    """Best-effort username extraction for profile-style social URLs."""
    if not source_url:
        return None
    try:
        host = (urlparse(source_url).hostname or "").lower()
        parts = [p for p in urlparse(source_url).path.split("/") if p]
        if not parts:
            return None
        # Only use the first path component for known social platforms.
        if host.endswith(("instagram.com", "threads.net", "twitter.com", "x.com", "tiktok.com")):
            reserved = {
                "reel", "reels", "p", "tv", "stories", "explore", "accounts",
                "share", "intent", "hashtag", "video", "photo", "status",
            }
            candidate = parts[0].lstrip("@")
            if candidate.lower() not in reserved and not candidate.isdigit():
                return _safe_filename_part(candidate)
    except (TypeError, ValueError):
        return None
    return None


def rename_downloaded_file(
    file_path: str,
    username: str | None = None,
    source_url: str | None = None,
) -> str:
    """Rename a downloaded file to '<username>_<original-name>.<ext>' safely.

    Returns the original path if the file is missing or already named accordingly.
    """
    if not file_path or not os.path.isfile(file_path):
        return file_path

    creator = _safe_filename_part(username or "") if username else None
    creator = creator or username_from_url(source_url) or "download"
    directory, filename = os.path.split(file_path)
    stem, extension = os.path.splitext(filename)
    safe_stem = _safe_filename_part(stem, "media")
    prefix = f"{creator}_"
    if safe_stem.lower().startswith(prefix.lower()):
        return file_path

    new_name = f"{prefix}{safe_stem}{extension}"
    target = os.path.join(directory, new_name)
    counter = 2
    while os.path.exists(target) and os.path.abspath(target) != os.path.abspath(file_path):
        target = os.path.join(directory, f"{prefix}{safe_stem}_{counter}{extension}")
        counter += 1
    if os.path.abspath(target) == os.path.abspath(file_path):
        return file_path
    os.replace(file_path, target)
    return target
