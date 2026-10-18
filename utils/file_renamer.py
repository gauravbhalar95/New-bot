"""Reusable helpers for naming downloaded media with its original uploader."""

import logging
import re
from pathlib import Path
from typing import Iterable

from utils.sanitize import sanitize_filename

logger = logging.getLogger(__name__)


def _clean_uploader(value: object) -> str:
    """Normalize a platform uploader/channel value into a safe filename prefix."""
    text = str(value or "").strip().lstrip("@")
    text = re.sub(r"\s+", " ", text)
    text = sanitize_filename(text, max_length=80).strip(" ._-")
    return text or "creator"


def rename_media_files(paths: Iterable[str | Path], uploader: object, identifier: object | None = None) -> list[Path]:
    """Prefix existing media files with the original uploader name.

    Keeps extensions, avoids double-prefixing, and handles duplicate names.
    Missing uploader metadata becomes "creator", never the requester username.
    """
    clean_uploader = _clean_uploader(uploader)
    clean_identifier = (
        sanitize_filename(str(identifier), max_length=80).strip(" ._- ")
        if identifier else ""
    )
    renamed: list[Path] = []
    used: set[str] = set()

    for value in paths:
        path = Path(value)
        if not path.is_file():
            continue

        suffix = path.suffix
        current_stem = path.stem
        prefix = f"{clean_uploader} - "
        if current_stem.casefold().startswith(prefix.casefold()):
            target = path
        else:
            stem = current_stem
            if clean_identifier and clean_identifier.casefold() not in stem.casefold():
                stem = f"{clean_identifier} - {stem}"
            target = path.with_name(sanitize_filename(f"{prefix}{stem}{suffix}", 240))

        counter = 2
        while target.exists() and target.resolve() != path.resolve():
            target = path.with_name(sanitize_filename(f"{clean_uploader} - {current_stem}_{counter}{suffix}", 240))
            counter += 1

        try:
            if target.resolve() != path.resolve():
                path.replace(target)
            key = str(target)
            if key not in used:
                renamed.append(target)
                used.add(key)
        except OSError as exc:
            logger.warning("Could not rename downloaded media %s: %s", path, exc)
            renamed.append(path)

    return renamed
