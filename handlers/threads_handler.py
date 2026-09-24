# handlers/threads_handler.py

import gc
import html
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
import yt_dlp

from config import DOWNLOAD_DIR
from utils.logger import setup_logging

logger = setup_logging(logging.DEBUG)

SUPPORTED_DOMAINS = {
    "threads.net",
    "www.threads.net",
    "threads.com",
    "www.threads.com",
}

MEDIA_EXTENSIONS = {
    ".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v",
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
}

THREADS_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)

Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)


def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return (
            result.scheme in {"http", "https"}
            and result.netloc.lower() in SUPPORTED_DOMAINS
        )
    except ValueError:
        return False


def _find_downloaded_files(info_dict) -> list[Path]:
    files: list[Path] = []
    entries = info_dict.get("entries") if isinstance(info_dict, dict) else None
    items = list(entries) if entries else [info_dict]

    for entry in items:
        if not entry:
            continue

        candidates = []
        for item in entry.get("requested_downloads") or []:
            filepath = item.get("filepath")
            if filepath and Path(filepath).is_file():
                candidates.append(Path(filepath))

        for key in ("_filename", "filename"):
            filepath = entry.get(key)
            if filepath and Path(filepath).is_file():
                candidates.append(Path(filepath))

        chosen = next(
            (p for p in candidates if p.suffix.lower() in MEDIA_EXTENSIONS),
            None,
        )
        if chosen and chosen not in files:
            files.append(chosen)

    return files


def _extract_image_urls(page_html: str) -> list[str]:
    """Extract public Threads image URLs from server-rendered HTML."""
    page_html = html.unescape(page_html).replace("\/", "/")
    found = []

    # og:image covers the common single-image post case.
    found.extend(
        re.findall(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
            page_html,
            re.IGNORECASE,
        )
    )

    # Also inspect embedded JSON for additional carousel image URLs.
    found.extend(
        re.findall(
            r'https?://[^"\\\'<> ]+?\.(?:jpe?g|png|webp|gif)(?:\?[^"\\\'<> ]*)?',
            page_html,
            re.IGNORECASE,
        )
    )

    urls = []
    seen = set()
    for image_url in found:
        image_url = image_url.replace("\u0026", "&").replace("\/", "/")
        if image_url.startswith("//"):
            image_url = "https:" + image_url
        if image_url.startswith("http") and image_url not in seen:
            seen.add(image_url)
            urls.append(image_url)

    return urls


def _download_images(url: str) -> list[Path]:
    headers = {
        "User-Agent": "Googlebot/2.1 (+http://www.google.com/bot.html)",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    }
    response = requests.get(url, headers=headers, timeout=25)
    response.raise_for_status()

    image_urls = _extract_image_urls(response.text)
    if not image_urls:
        return []

    downloaded = []
    post_id = urlparse(url).path.rstrip("/").split("/")[-1] or "post"

    for index, image_url in enumerate(image_urls, start=1):
        try:
            image_response = requests.get(
                image_url,
                headers={"User-Agent": THREADS_UA, "Referer": "https://www.threads.com/"},
                timeout=30,
                stream=True,
            )
            image_response.raise_for_status()

            content_type = image_response.headers.get("Content-Type", "").lower()
            extension = ".jpg"
            for candidate in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                if candidate in content_type:
                    extension = candidate
                    break

            output = Path(DOWNLOAD_DIR) / f"threads_{post_id}_{index}{extension}"
            with output.open("wb") as file:
                for chunk in image_response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        file.write(chunk)

            if output.is_file() and output.stat().st_size > 0:
                downloaded.append(output)
        except Exception as image_error:
            logger.warning("Failed to download Threads image %s: %s", image_url, image_error)

    return downloaded


def process_threads(url: str):
    """Download Threads videos/carousels through yt-dlp and images through fallback scraping."""
    url = url.split("#")[0]

    ydl_opts = {
        "format": "bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": str(Path(DOWNLOAD_DIR) / "threads_%(id)s_%(title)s.%(ext)s"),
        "noplaylist": False,
        "socket_timeout": 20,
        "retries": 5,
        "fragment_retries": 5,
        "quiet": True,
        "no_warnings": True,
        "http_headers": {
            "User-Agent": THREADS_UA,
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.threads.com/",
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

        media_paths = _find_downloaded_files(info_dict) if info_dict else []

        if media_paths:
            total_size = sum(p.stat().st_size for p in media_paths)
            logger.info(
                "Threads media ready: %s file(s), %.2f MB total",
                len(media_paths),
                total_size / (1024 ** 2),
            )
            return (
                [str(p) for p in media_paths]
                if len(media_paths) > 1
                else str(media_paths[0]),
                int(total_size),
                None,
            )

        raise RuntimeError("yt-dlp returned no Threads media files")

    except Exception as ytdlp_error:
        logger.warning("yt-dlp Threads extraction failed: %s", ytdlp_error)

        try:
            image_paths = _download_images(url)
            if image_paths:
                total_size = sum(p.stat().st_size for p in image_paths)
                logger.info(
                    "Threads image fallback ready: %s file(s), %.2f MB total",
                    len(image_paths),
                    total_size / (1024 ** 2),
                )
                return (
                    [str(p) for p in image_paths]
                    if len(image_paths) > 1
                    else str(image_paths[0]),
                    int(total_size),
                    None,
                )
        except Exception as image_error:
            logger.error("Threads image fallback failed: %s", image_error, exc_info=True)

        return None, 0, str(ytdlp_error)


def cleanup_media(media_path: str) -> None:
    try:
        path = Path(media_path)
        if path.exists():
            path.unlink()
            gc.collect()
    except Exception as e:
        logger.error("Failed to clean up %s: %s", media_path, e)
