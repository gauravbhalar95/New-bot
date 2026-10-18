import asyncio
import base64
import http.cookiejar
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import yt_dlp

from config import DOWNLOAD_DIR, X_FILE, FFMPEG_PATH
from utils.logger import setup_logging
from utils.thumb_generator import generate_thumbnail
from utils.file_renamer import rename_media_files

logger = setup_logging(logging.DEBUG)

# Optional proxy/VPN gateway for X only. Configure X_PROXY in Koyeb Secrets.
# Example: socks5h://user:password@proxy-host:1080 or http://proxy-host:8080
X_PROXY = os.getenv("X_PROXY") or os.getenv("VPN_PROXY_URL")


def _get_x_cookie_file():
    """
    Resolve the Netscape-format X login cookie file.

    On Koyeb, either mount/upload x.txt at X_FILE, set X_COOKIES_FILE to a
    readable cookie-file path, or store the base64-encoded Netscape cookie
    file in the X_COOKIES_B64 secret. Never commit login cookies to Git.
    """
    configured_path = os.getenv("X_COOKIES_FILE", "").strip()
    cookie_path = configured_path or X_FILE

    if os.path.isfile(cookie_path) and os.path.getsize(cookie_path) > 0:
        return cookie_path

    encoded_cookies = os.getenv("X_COOKIES_B64", "").strip()
    if encoded_cookies:
        try:
            cookie_bytes = base64.b64decode(encoded_cookies, validate=True)
            if b"# Netscape HTTP Cookie File" not in cookie_bytes[:512] and b"# HTTP Cookie File" not in cookie_bytes[:512]:
                logger.warning("X_COOKIES_B64 does not look like a Netscape-format cookie file.")
            target = Path(X_FILE)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(cookie_bytes)
            try:
                target.chmod(0o600)
            except OSError:
                pass
            if target.stat().st_size > 0:
                logger.info("Loaded X login cookies from the X_COOKIES_B64 secret.")
                return str(target)
        except (ValueError, OSError) as exc:
            logger.error("Could not load X_COOKIES_B64 secret: %s", exc)

    logger.warning(
        "X login cookies are unavailable. Provide a Netscape-format cookie file "
        "at %s or configure X_COOKIES_FILE/X_COOKIES_B64.",
        cookie_path,
    )
    return None


def _open_x_url(request, timeout=30):
    """Open an X request with login cookies and the optional configured proxy."""
    handlers = []
    if X_PROXY:
        handlers.append(urllib.request.ProxyHandler({"http": X_PROXY, "https": X_PROXY}))

    cookie_path = _get_x_cookie_file()
    if cookie_path:
        cookie_jar = http.cookiejar.MozillaCookieJar(cookie_path)
        try:
            cookie_jar.load(ignore_discard=True, ignore_expires=True)
            handlers.append(urllib.request.HTTPCookieProcessor(cookie_jar))
        except (http.cookiejar.LoadError, OSError) as exc:
            logger.warning("Could not parse X cookie file for HTTP fallback: %s", exc)

    opener = urllib.request.build_opener(*handlers)
    return opener.open(request, timeout=timeout)


def _tweet_id(url):
    match = re.search(r"(?:status|statuses)/(\d+)", url)
    return match.group(1) if match else None


def _download_tweet_images(url):
    """
    Fallback for X posts containing photos but no downloadable video.
    Returns a single image path, or a ZIP path for multiple images.
    """
    tweet_id = _tweet_id(url)
    if not tweet_id:
        logger.info("Cannot find X status ID for image fallback.")
        return None

    endpoint = (
        "https://cdn.syndication.twimg.com/tweet-result?"
        + urllib.parse.urlencode({"id": tweet_id, "lang": "en"})
    )
    request = urllib.request.Request(
        endpoint,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Referer": "https://x.com/",
            "Accept": "application/json",
        },
    )

    try:
        with _open_x_url(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        logger.warning("X image metadata fallback failed: %s", exc)
        return None

    photos = payload.get("photos") or []
    if not photos:
        for media in payload.get("mediaDetails") or []:
            if media.get("type") == "photo" and media.get("media_url_https"):
                photos.append({"url": media["media_url_https"]})

    if not photos:
        logger.info("X post metadata contains no photos.")
        return None

    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^0-9]", "", tweet_id)
    downloaded = []

    for index, photo in enumerate(photos, start=1):
        image_url = photo.get("url") or photo.get("media_url_https")
        if not image_url:
            continue

        parsed = urllib.parse.urlsplit(image_url)
        query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        query["name"] = "orig"
        image_url = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path,
             urllib.parse.urlencode(query), parsed.fragment)
        )

        image_request = urllib.request.Request(
            image_url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://x.com/",
            },
        )
        try:
            with _open_x_url(image_request, timeout=30) as response:
                data = response.read()
                content_type = response.headers.get("Content-Type", "").lower()
            if not data or not content_type.startswith("image/"):
                logger.warning("Skipping non-image response for X photo %s", index)
                continue

            extension = ".jpg"
            if "png" in content_type:
                extension = ".png"
            elif "webp" in content_type:
                extension = ".webp"

            image_path = os.path.join(
                DOWNLOAD_DIR, f"x_{safe_id}_image_{index}{extension}"
            )
            with open(image_path, "wb") as image_file:
                image_file.write(data)
            downloaded.append(image_path)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning("Could not download X photo %s: %s", index, exc)

    if not downloaded:
        return None

    if len(downloaded) == 1:
        return downloaded[0]

    archive_path = os.path.join(DOWNLOAD_DIR, f"x_{safe_id}_images.zip")
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for image_path in downloaded:
            archive.write(image_path, arcname=os.path.basename(image_path))
    logger.info("Downloaded %d X images into %s", len(downloaded), archive_path)
    return archive_path


def download_twitter_media(url):
    """
    Download X videos using login cookies. If no video is available, try
    public photo metadata and return a single image or ZIP for photo posts.
    Return contract: (file_path, file_size, thumbnail_path).
    """
    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
    output_path = os.path.join(DOWNLOAD_DIR, "%(title).100s [%(id)s].%(ext)s")
    cookie_path = _get_x_cookie_file()

    ydl_opts = {
        "outtmpl": output_path,
        "format": "bv+ba/b",
        "ffmpeg_location": FFMPEG_PATH,
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "continuedl": True,
        "quiet": True,
        "no_warnings": True,
        "logger": logger,
        "nocheckcertificate": True,
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://x.com/",
        },
    }
    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path
        logger.info("X yt-dlp authentication enabled using cookie file: %s", cookie_path)
    else:
        logger.warning("X yt-dlp is running without login cookies; protected posts may fail.")

    if X_PROXY:
        ydl_opts["proxy"] = X_PROXY
        logger.info("X download proxy is configured; routing X requests through proxy.")
    else:
        logger.info("No X proxy configured; using the server default network route.")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        if info:
            candidates = []
            for item in info.get("requested_downloads") or []:
                path = item.get("filepath") or item.get("_filename")
                if path:
                    candidates.append(path)
            prepared = ydl.prepare_filename(info)
            candidates.extend([
                info.get("filepath"),
                info.get("_filename"),
                prepared,
                os.path.splitext(prepared)[0] + ".mp4" if prepared else None,
            ])

            file_path = next(
                (path for path in candidates if path and os.path.isfile(path)
                 and os.path.getsize(path) > 0),
                None,
            )
            if file_path:
                renamed_paths = rename_media_files([file_path], info.get("uploader") or info.get("channel") or info.get("creator"), info.get("id"))
                file_path = str(renamed_paths[0]) if renamed_paths else file_path
                file_size = os.path.getsize(file_path)
                thumbnail_path = None
                try:
                    thumbnail_path = asyncio.run(generate_thumbnail(file_path))
                except Exception as thumb_error:
                    logger.warning("X video thumbnail generation failed: %s", thumb_error)
                logger.info("X video download completed: %s", file_path)
                return file_path, file_size, thumbnail_path

        logger.info("yt-dlp returned no downloaded video; trying X photo fallback.")

    except yt_dlp.DownloadError as exc:
        logger.warning("X video extraction/download unavailable; trying photo fallback: %s", exc)
    except Exception as exc:
        logger.warning("Unexpected X video download error; trying photo fallback: %s", exc)

    try:
        image_path = _download_tweet_images(url)
        if image_path and os.path.isfile(image_path) and os.path.getsize(image_path) > 0:
            from urllib.parse import urlparse
            author = urlparse(url).path.strip("/").split("/")[0] or "creator"
            renamed_paths = rename_media_files([image_path], author, urlparse(url).path.strip("/").split("/")[-1])
            image_path = str(renamed_paths[0]) if renamed_paths else image_path
            file_size = os.path.getsize(image_path)
            logger.info("X photo fallback completed: %s", image_path)
            return image_path, file_size, None
    except Exception as exc:
        logger.exception("X photo fallback failed: %s", exc)

    logger.error("No downloadable video or public photo media found for X URL: %s", url)
    return None, None, None
