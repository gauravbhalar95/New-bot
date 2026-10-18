"""Instaloader-based Instagram post downloader with lazy imports.

Downloads all images/videos in a public post or carousel. A configured
Instagram session may also allow access to media requiring authentication.
"""
import re
import shutil
import tempfile
from pathlib import Path

from config import DOWNLOAD_DIR, INSTAGRAM_SESSIONID, INSTAGRAM_USERNAME

MEDIA_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".m4v"}


def _shortcode(url: str) -> str:
    match = re.search(r"/(?:p|reel|tv)/([^/?#]+)/?", url)
    if not match:
        raise ValueError("Could not find Instagram post shortcode in URL")
    return match.group(1)


def _configure_loader(instaloader_module):
    """Create an Instaloader instance only when a post download is requested."""
    loader = instaloader_module.Instaloader(
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
    sessionid = (INSTAGRAM_SESSIONID or "").strip()
    if sessionid:
        loader.context._session.cookies.set(
            "sessionid", sessionid, domain=".instagram.com", path="/"
        )
        loader.context._session.cookies.set(
            "sessionid", sessionid, domain="instagram.com", path="/"
        )
        loader.context.username = INSTAGRAM_USERNAME or "session"
    return loader


def download_instagram_post(url: str) -> list[Path]:
    """Download every image/video from an Instagram post or carousel."""
    # Heavy third-party dependency is imported only when this function is called.
    import instaloader

    shortcode = _shortcode(url)
    output_root = Path(DOWNLOAD_DIR)
    output_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"instaloader_{shortcode}_") as temp:
        loader = _configure_loader(instaloader)
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        username = (
            getattr(post, "owner_username", None)
            or getattr(getattr(post, "owner_profile", None), "username", None)
            or "instagram"
        )
        target_dir = Path(temp) / str(username)
        target_dir.mkdir(parents=True, exist_ok=True)
        loader.download_post(post, target=str(target_dir))

        media = sorted(
            path for path in target_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS
        )
        if not media:
            raise RuntimeError("Instagram post download completed without media files")

        safe_user = re.sub(r"[^A-Za-z0-9._-]+", "_", str(username)).strip("._-") or "instagram"
        safe_shortcode = re.sub(r"[^A-Za-z0-9_-]+", "_", shortcode) or "post"
        results: list[Path] = []
        for index, source in enumerate(media, start=1):
            stem = f"{safe_user} - {safe_shortcode}"
            if len(media) > 1:
                stem += f"_{index}"
            destination = output_root / f"{stem}{source.suffix.lower()}"
            counter = 2
            while destination.exists():
                destination = output_root / f"{stem}_{counter}{source.suffix.lower()}"
                counter += 1
            shutil.copy2(source, destination)
            if destination.is_file() and destination.stat().st_size > 0:
                results.append(destination)

        if not results:
            raise RuntimeError("Instagram media files could not be copied")
        return results
