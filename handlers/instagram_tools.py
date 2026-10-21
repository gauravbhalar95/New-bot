"""Extra Instagram media tools. Kept separate from handlers.instagram_handler."""
from pathlib import Path
from urllib.parse import urlparse
import re

from config import DOWNLOAD_DIR, INSTAGRAM_SESSIONID, INSTAGRAM_USERNAME


def _loader():
    import instaloader

    loader = instaloader.Instaloader(
        download_pictures=True,
        download_videos=True,
        download_video_thumbnails=False,
        save_metadata=False,
        compress_json=False,
        download_geotags=False,
        post_metadata_txt_pattern=None,
        storyitem_metadata_txt_pattern=None,
        quiet=True,
    )
    session = (INSTAGRAM_SESSIONID or "").strip()
    if session:
        loader.context._session.cookies.set(
            "sessionid", session, domain=".instagram.com", path="/"
        )
        loader.context._session.cookies.set(
            "sessionid", session, domain="instagram.com", path="/"
        )
        loader.context.username = INSTAGRAM_USERNAME or "session"
    return instaloader, loader


def _username(value: str) -> str:
    value = (value or "").strip()
    if "://" in value:
        parsed = urlparse(value)
        parts = [part for part in parsed.path.split("/") if part]
        value = parts[0] if parts else ""
    value = value.lstrip("@").strip("/")
    if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", value):
        raise ValueError("Send a valid Instagram username or profile URL.")
    return value


def download_instagram_dp(target: str) -> str:
    """Download a profile's current HD profile picture to DOWNLOAD_DIR."""
    instaloader, loader = _loader()
    username = _username(target)
    profile = instaloader.Profile.from_username(loader.context, username)
    output = Path(DOWNLOAD_DIR)
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f"{username}_profile.jpg"
    import requests
    response = requests.get(profile.profile_pic_url, timeout=30)
    response.raise_for_status()
    if not response.content:
        raise RuntimeError("Instagram returned an empty profile image.")
    destination.write_bytes(response.content)
    return str(destination)


def download_instagram_stories(target: str) -> list[str]:
    """Download currently available stories for a username/profile URL."""
    instaloader, loader = _loader()
    username = _username(target)
    profile = instaloader.Profile.from_username(loader.context, username)
    output = Path(DOWNLOAD_DIR)
    output.mkdir(parents=True, exist_ok=True)
    target_dir = output / f"story_{username}"
    target_dir.mkdir(parents=True, exist_ok=True)

    count_before = {p.resolve() for p in target_dir.rglob("*") if p.is_file()}
    # Stories require an authenticated session and the account must be accessible.
    loader.download_stories(userids=[profile.userid], filename_target=str(target_dir))
    files = [
        str(p) for p in target_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".mp4"}
        and p.resolve() not in count_before and p.stat().st_size > 0
    ]
    if not files:
        raise RuntimeError(
            "No story media found. Stories may have expired, or Instagram login/session access is required."
        )
    return sorted(files)
