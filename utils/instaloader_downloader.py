"""Instaloader-based Instagram fallback downloader.

Used when yt-dlp/instagrapi cannot retrieve an Instagram post.  The helper
supports public posts without credentials and can optionally reuse the
INSTAGRAM_SESSIONID environment variable for authenticated posts.
"""

import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import instaloader

from config import DOWNLOAD_DIR, INSTAGRAM_SESSIONID, INSTAGRAM_USERNAME


MEDIA_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".m4v"}


def _shortcode(url: str) -> str:
    match = re.search(r"/(?:p|reel|tv)/([^/?#]+)/?", url)
    if not match:
        raise ValueError("Could not find Instagram shortcode in URL")
    return match.group(1)


def _configure_loader() -> instaloader.Instaloader:
    loader = instaloader.Instaloader(
        download_pictures=True,
        download_videos=True,
        download_video_thumbnails=False,
        save_metadata=False,
        compress_json=False,
        download_geotags=False,
        post_metadata_txt_pattern=None,
        storyitem_metadata_txt_pattern=None,
        dirname_pattern="{target}",
        filename_pattern="{shortcode}_{date_utc}",
        quiet=True,
    )

    # A sessionid is useful for private/authenticated media.  We deliberately
    # do not log the value.  Public posts can still work without a session.
    sessionid = (INSTAGRAM_SESSIONID or "").strip()
    if sessionid:
        loader.context._session.cookies.set(
            "sessionid",
            sessionid,
            domain=".instagram.com",
            path="/",
        )
        loader.context._session.cookies.set(
            "sessionid",
            sessionid,
            domain="instagram.com",
            path="/",
        )

    return loader


def download_instagram_post(url: str) -> list[Path]:
    """Download every picture/video from one Instagram post or reel."""
    shortcode = _shortcode(url)
    output_root = Path(DOWNLOAD_DIR)
    output_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"instaloader_{shortcode}_") as temp:
        temp_dir = Path(temp)
        loader = _configure_loader()
        post = instaloader.Post.from_shortcode(loader.context, shortcode)

        username = (
            getattr(post, "owner_username", None)
            or getattr(getattr(post, "owner_profile", None), "username", None)
            or "instagram"
        )

        target_dir = temp_dir / str(username)
        target_dir.mkdir(parents=True, exist_ok=True)

        loader.download_post(post, target=str(target_dir))

        media = sorted(
            p for p in target_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS
        )

        if not media:
            raise RuntimeError("Instaloader completed but returned no media files")

        safe_user = re.sub(r"[^A-Za-z0-9._-]+", "_", str(username)).strip("._-") or "instagram"
        safe_shortcode = re.sub(r"[^A-Za-z0-9_-]+", "_", shortcode) or "post"

        result = []
        for index, source in enumerate(media, start=1):
            suffix = source.suffix.lower()
            stem = f"{safe_user} - {safe_shortcode}"
            if len(media) > 1:
                stem += f"_{index}"

            destination = output_root / f"{stem}{suffix}"
            counter = 2
            while destination.exists():
                destination = output_root / f"{stem}_{counter}{suffix}"
                counter += 1

            shutil.copy2(source, destination)
            if destination.is_file() and destination.stat().st_size > 0:
                result.append(destination)

        if not result:
            raise RuntimeError("Instaloader downloaded media but files could not be copied")

        return result
