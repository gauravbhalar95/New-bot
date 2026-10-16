"""HTTP API for the public YouTube downloader page."""
import asyncio
import logging
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from quart import Blueprint, jsonify, request

from handlers.youtube_handler import process_youtube
from utils.browser_downloads import register_download

logger = logging.getLogger(__name__)
downloader_api = Blueprint("downloader_api", __name__)
RATE_WINDOW_SECONDS = 600
RATE_MAX_REQUESTS = 5
_requests_by_ip = defaultdict(deque)


def _allowed_youtube_url(url):
    if not isinstance(url, str) or len(url) > 2048:
        return False
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    return host in {
        "youtu.be", "youtube.com", "www.youtube.com", "m.youtube.com",
        "music.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com",
    } or host.endswith(".youtube.com")


def _rate_limited(ip):
    now = time.monotonic()
    bucket = _requests_by_ip[ip]
    while bucket and now - bucket[0] > RATE_WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= RATE_MAX_REQUESTS:
        return True
    bucket.append(now)
    return False


@downloader_api.post("/api/download/youtube")
async def download_youtube_api():
    payload = await request.get_json(silent=True) or {}
    url = payload.get("url", "")
    quality = payload.get("quality") or None

    if not _allowed_youtube_url(url):
        return jsonify({"error": "માન્ય YouTube વિડિયો URL મોકલો."}), 400

    if quality is not None and str(quality) not in {
        "best", "144", "240", "360", "480", "720", "1080", "1440", "2160"
    }:
        return jsonify({"error": "આ video quality supported નથી."}), 400
    if quality == "best":
        quality = None

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
    ip = ip.split(",", 1)[0].strip()[:100]
    if _rate_limited(ip):
        return jsonify({"error": "ઘણા પ્રયાસ થયા છે. 10 મિનિટ પછી ફરી પ્રયાસ કરો."}), 429

    try:
        file_path, file_size, error = await asyncio.to_thread(
            process_youtube, url.strip(), quality
        )
        if error or not file_path:
            return jsonify({"error": error or "ડાઉનલોડ નિષ્ફળ ગયું."}), 422

        token = register_download(file_path)
        return jsonify({
            "ok": True,
            "filename": file_path.rsplit("/", 1)[-1],
            "size_bytes": file_size,
            "download_url": f"/download/{token}",
        }), 200
    except Exception:
        logger.exception("Web downloader request failed")
        return jsonify({"error": "સર્વર પર ડાઉનલોડ નિષ્ફળ ગયું. થોડા સમય પછી ફરી પ્રયાસ કરો."}), 500
