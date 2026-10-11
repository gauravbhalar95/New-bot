"""Temporary, token-protected browser download links for files stored on this Koyeb instance."""
import secrets
import threading
import time
from pathlib import Path

TTL_SECONDS = 24 * 60 * 60
_lock = threading.Lock()
_items = {}


def register_download(file_path):
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError("The downloaded file is no longer available.")
    token = secrets.token_urlsafe(32)
    now = time.time()
    with _lock:
        for old_token in [key for key, item in _items.items() if item["expires"] <= now]:
            _items.pop(old_token, None)
        _items[token] = {
            "path": str(path),
            "name": path.name,
            "size": path.stat().st_size,
            "expires": now + TTL_SECONDS,
        }
    return token


def is_registered_path(file_path):
    resolved = str(Path(file_path).resolve())
    now = time.time()
    with _lock:
        expired = [key for key, item in _items.items() if item["expires"] <= now]
        for key in expired:
            _items.pop(key, None)
        return any(item["path"] == resolved for item in _items.values())


def get_download(token):
    with _lock:
        item = _items.get(token)
        if not item or item["expires"] <= time.time():
            _items.pop(token, None)
            return None
        if not Path(item["path"]).is_file():
            _items.pop(token, None)
            return None
        return dict(item)
