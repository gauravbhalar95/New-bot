"""Admin-uploaded cookie-file validation and secure storage.

Cookie files are credentials. Never log their contents or commit them to Git.
"""
import os
import tempfile
from pathlib import Path

from config import FACEBOOK_FILE, INSTAGRAM_FILE, X_FILE, YOUTUBE_FILE

MAX_COOKIE_BYTES = 2 * 1024 * 1024

COOKIE_TARGETS = {
    "youtube_cookies.txt": {
        "platform": "YouTube",
        "path": YOUTUBE_FILE,
        "domains": ("youtube.com", "google.com", "googlevideo.com", "youtube-nocookie.com"),
    },
    "youtube-cookies.txt": {
        "platform": "YouTube",
        "path": YOUTUBE_FILE,
        "domains": ("youtube.com", "google.com", "googlevideo.com", "youtube-nocookie.com"),
    },
    "x.txt": {
        "platform": "X/Twitter",
        "path": X_FILE,
        "domains": ("x.com", "twitter.com", "twimg.com", "t.co"),
    },
    "facebook.txt": {
        "platform": "Facebook",
        "path": FACEBOOK_FILE,
        "domains": ("facebook.com", "fb.com", "fbcdn.net", "messenger.com"),
    },
    "instagram_cookies.txt": {
        "platform": "Instagram",
        "path": INSTAGRAM_FILE,
        "domains": ("instagram.com", "cdninstagram.com"),
    },
    "instagram-cookies.txt": {
        "platform": "Instagram",
        "path": INSTAGRAM_FILE,
        "domains": ("instagram.com", "cdninstagram.com"),
    },
    "instagram.txt": {
        "platform": "Instagram",
        "path": INSTAGRAM_FILE,
        "domains": ("instagram.com", "cdninstagram.com"),
    },
}


def get_cookie_target(filename: str):
    """Resolve only explicitly supported cookie filenames."""
    return COOKIE_TARGETS.get(Path(filename or "").name.lower())


def validate_cookie_data(data: bytes, allowed_domains: tuple[str, ...]) -> bool:
    """Require a non-empty Netscape cookie export with a matching domain."""
    if not data or len(data) > MAX_COOKIE_BYTES:
        return False

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False

    lines = text.splitlines()
    rows = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < 7:
            continue
        domain = columns[0].strip().lower().lstrip(".")
        if domain:
            rows.append(domain)

    if not rows:
        return False

    return any(
        domain == allowed or domain.endswith("." + allowed)
        for domain in rows
        for allowed in allowed_domains
    )


def install_cookie_file(filename: str, data: bytes) -> str:
    """Validate and atomically save a platform cookie file with mode 0600."""
    target = get_cookie_target(filename)
    if not target:
        raise ValueError(
            "Unsupported filename. Send youtube_cookies.txt, x.txt, "
            "facebook.txt, or instagram_cookies.txt."
        )
    if len(data or b"") > MAX_COOKIE_BYTES:
        raise ValueError("Cookie file is too large (maximum 2 MB).")
    if not validate_cookie_data(data, target["domains"]):
        raise ValueError(
            f"Invalid {target['platform']} cookie file. Export cookies in Netscape "
            "cookies.txt format for the matching platform."
        )

    destination = Path(target["path"]).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=".cookie-upload-", suffix=".tmp", dir=str(destination.parent)
    )
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, destination)
        try:
            os.chmod(destination, 0o600)
        except OSError:
            pass
    finally:
        try:
            if os.path.exists(temp_name):
                os.remove(temp_name)
        except OSError:
            pass

    return target["platform"]


def cookie_file_status():
    """Return metadata only; never return cookie values."""
    result = {}
    for filename, target in COOKIE_TARGETS.items():
        # Report each canonical filename once.
        platform = target["platform"]
        if platform in result:
            continue
        path = Path(target["path"])
        exists = path.is_file()
        result[platform] = {
            "exists": exists,
            "size": path.stat().st_size if exists else 0,
        }
    return result
