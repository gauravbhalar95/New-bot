"""Safe filename utilities for downloaded media and directory cleanup."""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from urllib.parse import urlparse

from utils.sanitize import sanitize_filename

logger = logging.getLogger(__name__)


def _safe_filename_part(value: str, fallback: str = "download") -> str:
    """Return a short, filesystem-safe filename component."""
    value = unicodedata.normalize("NFKC", str(value or ""))
    value = re.sub(r'[\\\\/:*?"<>|\\x00-\\x1f]', "", value)
    value = re.sub(r"\\s+", "_", value.strip())
    value = re.sub(r"[^\\w.\\-]", "", value, flags=re.UNICODE)
    value = value.strip(" ._-")
    return value[:80] or fallback


def username_from_url(source_url: str | None) -> str | None:
    """Best-effort username extraction for supported social URLs."""
    if not source_url:
        return None
    try:
        parsed = urlparse(source_url)
        host = (parsed.hostname or "").lower()
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            return None
        if host.endswith((
            "instagram.com", "threads.net", "twitter.com", "x.com", "tiktok.com"
        )):
            reserved = {
                "reel", "reels", "p", "tv", "stories", "explore", "accounts",
                "share", "intent", "hashtag", "video", "photo", "status",
            }
            candidate = parts[0].lstrip("@")
            if candidate.lower() not in reserved and not candidate.isdigit():
                return _safe_filename_part(candidate)
    except (TypeError, ValueError):
        logger.debug("Could not extract username from source URL", exc_info=True)
    return None


def _unique_target(directory: str, filename: str, original_path: str) -> str:
    """Avoid overwriting another file when a sanitized name already exists."""
    target = os.path.join(directory, filename)
    if os.path.abspath(target) == os.path.abspath(original_path) or not os.path.exists(target):
        return target

    stem, extension = os.path.splitext(filename)
    counter = 2
    while True:
        candidate = os.path.join(directory, f"{stem}_{counter}{extension}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def rename_file(old_path: str, new_path: str) -> bool:
    """Rename a file, logging failures and returning whether it succeeded."""
    try:
        if os.path.abspath(old_path) == os.path.abspath(new_path):
            return True
        if os.path.exists(new_path):
            logger.warning("Skipping rename because target already exists: %s", new_path)
            return False
        os.rename(old_path, new_path)
        logger.info("Renamed: %s -> %s", old_path, new_path)
        return True
    except OSError:
        logger.exception("Failed to rename %s -> %s", old_path, new_path)
        return False


def rename_files_in_directory(directory: str) -> dict[str, str]:
    """Sanitize filenames in one directory, preserving original names where safe.

    Subdirectories are not traversed. Existing destination files are never
    overwritten; a numeric suffix is used to avoid filename collisions.
    """
    if not os.path.isdir(directory):
        logger.warning("Directory not found: %s", directory)
        return {}

    renamed_files: dict[str, str] = {}
    filenames = sorted(
        name for name in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, name))
    )

    for filename in filenames:
        old_path = os.path.join(directory, filename)
        new_filename = sanitize_filename(filename)
        if new_filename == filename:
            logger.info("Keeping original filename: %s", old_path)
            continue

        target = _unique_target(directory, new_filename, old_path)
        if rename_file(old_path, target):
            renamed_files[filename] = os.path.basename(target)

    if not filenames:
        logger.info("No files found in directory: %s", directory)
    return renamed_files


def rename_downloaded_file(
    file_path: str,
    username: str | None = None,
    source_url: str | None = None,
) -> str:
    """Sanitize a downloaded filename and prefix it with its creator when known.

    Keeps the existing API used by bot.py. If a username cannot be found,
    uses 'download' as the prefix. Returns the original path on failure.
    """
    if not file_path or not os.path.isfile(file_path):
        return file_path

    directory, filename = os.path.split(file_path)
    safe_filename = sanitize_filename(filename)
    stem, extension = os.path.splitext(safe_filename)
    creator = (
        _safe_filename_part(username) if username else None
    ) or username_from_url(source_url) or "download"
    prefix = f"{creator}_"

    if stem.lower().startswith(prefix.lower()):
        target_name = safe_filename
    else:
        target_name = f"{prefix}{stem}{extension}"

    target = _unique_target(directory, target_name, file_path)
    if os.path.abspath(target) == os.path.abspath(file_path):
        return file_path
    if rename_file(file_path, target):
        return target
    return file_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Sanitize filenames in a directory without generic renaming."
    )
    parser.add_argument("directory", help="Directory containing files to sanitize")
    args = parser.parse_args()

    changes = rename_files_in_directory(args.directory)
    if changes:
        print("Renamed files:")
        for old_name, new_name in changes.items():
            print(f"{old_name} -> {new_name}")
    else:
        print("No files were renamed.")
