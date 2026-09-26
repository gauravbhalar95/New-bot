# handlers/instagram_handler.py

import gc
import html
import logging
import re
import requests
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Tuple, Union

import yt_dlp
from instagrapi import Client

from config import DOWNLOAD_DIR, COOKIES_FILE, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, INSTAGRAM_SESSIONID
from utils.logger import setup_logging


logger = setup_logging(logging.DEBUG)

logger.add(
    "instagram_handler.log",
    rotation="10 MB",
    level="DEBUG"
)

SUPPORTED_DOMAINS = ["instagram.com"]

Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)


def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return (
            result.scheme in ["http", "https"]
            and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
        )
    except ValueError:
        return False


def is_instagram_video(url: str) -> bool:
    return any(x in url for x in ["/reel/", "/tv/", "/video/"])


def download_progress_hook(d: dict) -> None:
    status = d.get("status")

    if status == "downloading":
        logger.info(
            "Downloading... %s at %s, ETA: %s",
            d.get("_percent_str", "0%"),
            d.get("_speed_str", "N/A"),
            d.get("_eta_str", "N/A"),
        )
    elif status == "finished":
        logger.info("✅ Download finished: %s", d.get("filename"))



def _download_image_instagrapi(url: str) -> list[Path]:
    """Download Instagram photo/carousel media using instagrapi."""
    try:
        client = Client()
        client.delay_range = [1, 2]
        client.read_timeout = 30
        media_pk = client.media_pk_from_url(url)
        media = client.media_info(media_pk)
        media_type = getattr(media, "media_type", None)
        logger.info("Instagram image handler: media_pk=%s media_type=%s", media_pk, media_type)
        if media_type == 1:
            path = client.photo_download(media_pk, folder=DOWNLOAD_DIR, overwrite=True)
            return [Path(path)] if path and Path(path).is_file() else []
        if media_type == 8:
            paths = client.album_download(media_pk, folder=DOWNLOAD_DIR, overwrite=True)
            return [Path(path) for path in paths if path and Path(path).is_file()]
        return []
    except Exception as e:
        logger.warning("instagrapi image handler failed for %s: %s", url, e)
        return []

def _download_image_fallback(url: str, cookie_path: Path) -> list[Path]:
    """Download Instagram post images when the post has no video."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
        "Referer": "https://www.instagram.com/",
    }

    cookies = {}
    try:
        import http.cookiejar
        jar = http.cookiejar.MozillaCookieJar(str(cookie_path))
        jar.load(ignore_discard=True, ignore_expires=True)
        cookies = {cookie.name: cookie.value for cookie in jar}
    except Exception as cookie_error:
        logger.debug("Instagram image fallback cookie load failed: %s", cookie_error)

    response = requests.get(
        url,
        headers=headers,
        cookies=cookies,
        timeout=25,
    )
    response.raise_for_status()

    page_html = html.unescape(response.text).replace("\\/", "/")
    image_urls = []

    # Handle both <meta property="og:image" content="..."> and
    # <meta content="..." property="og:image">.
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+property=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']twitter:image["\']',
        r'"display_url"\s*:\s*"([^"]+)"',
        r'"thumbnail_src"\s*:\s*"([^"]+)"',
    ]

    for pattern in patterns:
        image_urls.extend(re.findall(pattern, page_html, re.IGNORECASE))

    unique_urls = []
    seen = set()

    for image_url in image_urls:
        image_url = (
            image_url
            .replace("\\u0026", "&")
            .replace("\\/", "/")
            .replace("\\u002F", "/")
        )
        if image_url.startswith("//"):
            image_url = "https:" + image_url
        if image_url.startswith("http") and image_url not in seen:
            seen.add(image_url)
            unique_urls.append(image_url)

    if not unique_urls:
        logger.warning("Instagram image fallback found no image URL for %s", url)
        return []

    post_id = urlparse(url).path.rstrip("/").split("/")[-1] or "post"
    downloaded = []

    for index, image_url in enumerate(unique_urls, start=1):
        try:
            image_response = requests.get(
                image_url,
                headers=headers,
                cookies=cookies,
                timeout=30,
                stream=True,
            )
            image_response.raise_for_status()

            content_type = image_response.headers.get("Content-Type", "").lower()
            extension = ".jpg"
            for candidate in (".jpg", ".jpeg", ".png", ".webp"):
                if candidate in content_type:
                    extension = candidate
                    break

            output = Path(DOWNLOAD_DIR) / f"instagram_{post_id}_{index}{extension}"

            with output.open("wb") as file:
                for chunk in image_response.iter_content(chunk_size=262144):
                    if chunk:
                        file.write(chunk)

            if output.is_file() and output.stat().st_size > 0:
                downloaded.append(output)

        except Exception as image_error:
            logger.warning(
                "Instagram image fallback failed for %s: %s",
                image_url,
                image_error,
            )

    return downloaded


def _get_ffmpeg_path() -> Optional[str]:
    """Find a usable FFmpeg binary from the system or imageio-ffmpeg."""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_path and Path(ffmpeg_path).is_file():
            return ffmpeg_path
    except Exception as e:
        logger.debug("imageio-ffmpeg lookup failed: %s", e)
    return None


def _merge_video_audio(info_dict) -> Optional[Path]:
    """Explicitly mux separate yt-dlp video/audio files into one MP4."""
    if not isinstance(info_dict, dict):
        return None
    ffmpeg = _get_ffmpeg_path()
    if not ffmpeg:
        logger.warning("FFmpeg not found; cannot explicitly merge Instagram video/audio")
        return None
    entries = info_dict.get("entries") or [info_dict]
    for entry in entries:
        if not entry:
            continue
        requested = entry.get("requested_downloads") or []
        files = []
        for item in requested:
            filepath = item.get("filepath")
            if filepath and Path(filepath).is_file():
                files.append((item, Path(filepath)))
        video = next((path for item, path in files if item.get("vcodec") not in (None, "none")), None)
        audio = next((path for item, path in files if item.get("acodec") not in (None, "none") and item.get("vcodec") in (None, "none")), None)
        if not video or not audio:
            continue
        output = video.with_name(video.stem + "_merged.mp4")
        try:
            subprocess.run([
                ffmpeg, "-y", "-i", str(video), "-i", str(audio),
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", str(output),
            ], capture_output=True, text=True, timeout=900, check=True)
            if output.is_file() and output.stat().st_size > 0:
                for source in (video, audio):
                    try:
                        source.unlink()
                    except OSError:
                        pass
                logger.info("✅ FFmpeg merged Instagram video + audio: %s", output)
                return output
        except subprocess.CalledProcessError as e:
            logger.error("FFmpeg Instagram merge failed: %s", e.stderr[-3000:] if e.stderr else e)
        except Exception as e:
            logger.error("Instagram FFmpeg merge error: %s", e, exc_info=True)
    return None


def _find_downloaded_files(info_dict) -> list[Path]:
    """Find all final media files produced by yt-dlp, including carousels."""
    files = []

    entries = info_dict.get("entries") if isinstance(info_dict, dict) else None
    items = list(entries) if entries else [info_dict]

    for entry in items:
        if not entry:
            continue

        requested = entry.get("requested_downloads") or []
        candidates = []

        for item in requested:
            filepath = item.get("filepath")
            if filepath and Path(filepath).is_file():
                candidates.append(Path(filepath))

        for key in ("_filename", "filename"):
            filepath = entry.get(key)
            if filepath and Path(filepath).is_file():
                candidates.append(Path(filepath))

        # Prefer the merged MP4 over source streams.
        mp4 = next(
            (p for p in candidates if p.suffix.lower() == ".mp4"),
            None,
        )
        chosen = mp4 or (candidates[0] if candidates else None)

        if chosen and chosen.is_file() and chosen not in files:
            files.append(chosen)

    return files


def process_instagram(
    url: str
) -> Tuple[Optional[Union[str, list]], int, Optional[str]]:

    url = url.split("#")[0]

    cookie_path = Path(COOKIES_FILE)

    if not cookie_path.exists() or cookie_path.stat().st_size == 0:
        logger.error("❌ Instagram cookies file is missing or empty!")
        return None, 0, "Instagram cookies file is missing or empty"

    outtmpl = str(
        Path(DOWNLOAD_DIR) / "%(uploader)s - %(title)s.%(ext)s"
    )

    ydl_opts = {
        # Download both streams when Instagram exposes separate video/audio.
        # FFmpeg only muxes them; it does not re-encode the video here.
        "format": "best",
        "merge_output_format": "mp4",
        "outtmpl": outtmpl,
        "socket_timeout": 20,
        "retries": 5,
        "fragment_retries": 5,
        "progress_hooks": [download_progress_hook],
        "cookiefile": str(cookie_path),
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; "
                "rv:123.0 Gecko/20100101 Firefox/123.0"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.instagram.com/",
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

        if not info_dict:
            return None, 0, "❌ Failed to extract info"

        merged_path = _merge_video_audio(info_dict)
        video_paths = [merged_path] if merged_path else _find_downloaded_files(info_dict)

        # Single-item fallback: find the newest media file if yt-dlp did not
        # expose a final filepath.
        if not video_paths:
            media_extensions = {
                ".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"
            }
            candidates = sorted(
                (
                    p for p in Path(DOWNLOAD_DIR).iterdir()
                    if p.is_file() and p.suffix.lower() in media_extensions
                ),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                video_paths = [candidates[0]]

        if not video_paths:
            logger.error("❌ Instagram download completed but no media file was found.")
            return (
                None,
                0,
                "❌ Download completed, but the media file could not be found.",
            )

        total_size = sum(p.stat().st_size for p in video_paths)

        if len(video_paths) > 1:
            logger.info(
                "✅ Instagram carousel downloaded: %s media files, %.2f MB total",
                len(video_paths),
                total_size / (1024 ** 2),
            )
            return [str(p) for p in video_paths], int(total_size), None

        video_path = video_paths[0]
        logger.info(
            "✅ Final Instagram video ready: %s (%.2f MB)",
            video_path,
            video_path.stat().st_size / (1024 ** 2),
        )

        if video_path.suffix.lower() == ".mp4":
            logger.info(
                "✅ MP4 contains merged video/audio when separate audio was available."
            )

        return str(video_path), int(video_path.stat().st_size), None

    except yt_dlp.utils.DownloadError as e:
        logger.error("❌ Instagram download error: %s", e, exc_info=True)

        # /p/ posts can contain only images. Fall back when yt-dlp
        # explicitly reports that the post has no video.
        error_text = str(e).lower()
        if "no video formats found" in error_text or "there is no video" in error_text:
            try:
                image_paths = _download_image_instagrapi(url)
                if not image_paths:
                    image_paths = _download_image_fallback(url, cookie_path)
                if image_paths:
                    total_size = sum(p.stat().st_size for p in image_paths)
                    logger.info(
                        "✅ Instagram image fallback ready: %s file(s), %.2f MB total",
                        len(image_paths),
                        total_size / (1024 ** 2),
                    )
                    return (
                        [str(p) for p in image_paths]
                        if len(image_paths) > 1 else str(image_paths[0]),
                        int(total_size),
                        None,
                    )
            except Exception as image_error:
                logger.warning(
                    "Instagram image fallback failed: %s",
                    image_error,
                    exc_info=True,
                )

        return None, 0, str(e)

    except Exception as e:
        logger.exception("⚠️ Unexpected Instagram error: %s", e)
        return None, 0, str(e)




def _instagram_login() -> Client:
    """Create an authenticated Instagram client for story/profile requests.

    Prefer a session ID because password login may trigger Instagram 2FA/challenges
    on cloud IPs. The session ID must be supplied as a Koyeb secret.
    """
    client = Client()
    client.delay_range = [1, 2]
    client.read_timeout = 30

    if INSTAGRAM_SESSIONID:
        try:
            client.login_by_sessionid(INSTAGRAM_SESSIONID)
            logger.info("Instagram authenticated using session ID.")
            return client
        except Exception as session_error:
            logger.warning(
                "Instagram session ID authentication failed: %s",
                session_error,
            )

    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        raise RuntimeError(
            "Instagram authentication is not configured. Set INSTAGRAM_SESSIONID "
            "or INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD."
        )

    try:
        client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        logger.info("Instagram authenticated using username/password.")
        return client
    except Exception as login_error:
        raise RuntimeError(
            "Instagram login failed. Instagram requested 2-step verification or "
            "blocked this cloud login. Set a fresh INSTAGRAM_SESSIONID Koyeb secret."
        ) from login_error

def _instagram_username_from_input(value: str) -> str:
    """Extract a clean Instagram username from a username/profile/story input."""
    value = value.strip().strip("/")
    if value.startswith("@"):
        value = value[1:]

    if "instagram.com" in value.lower():
        parsed = urlparse(value)
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            raise ValueError("Instagram username was not found in the URL.")

        # /stories/<username>/... or /story/<username>/...
        if parts[0].lower() in {"stories", "story"} and len(parts) >= 2:
            value = parts[1]
        else:
            value = parts[0]

    value = value.split("?")[0].split("#")[0].strip("@/")
    if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", value):
        raise ValueError("Invalid Instagram username.")
    return value


def download_instagram_stories(value: str) -> list[str]:
    """Download all currently available stories for an Instagram user."""
    username = _instagram_username_from_input(value)
    client = _instagram_login()

    user_id = client.user_id_from_username(username)
    stories = client.user_stories(user_id)

    if not stories:
        raise RuntimeError(f"No active stories found for @{username}.")

    output_dir = Path(DOWNLOAD_DIR) / "story"
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []

    for index, story in enumerate(stories, start=1):
        try:
            path = client.story_download(
                story.pk,
                folder=str(output_dir),
            )
            if path and Path(path).is_file():
                downloaded.append(str(path))
                logger.info(
                    "Instagram story %s/%s downloaded for @%s: %s",
                    index, len(stories), username, path,
                )
        except Exception as story_error:
            logger.warning(
                "Failed to download story %s for @%s: %s",
                getattr(story, "pk", "?"),
                username,
                story_error,
            )

    if not downloaded:
        raise RuntimeError(f"Instagram stories for @{username} could not be downloaded.")

    return downloaded


def download_instagram_dp(value: str) -> str:
    """Download the highest-resolution Instagram profile picture available."""
    username = _instagram_username_from_input(value)
    client = _instagram_login()
    user = client.user_info_by_username(username)

    image_url = getattr(user, "profile_pic_url_hd", None) or getattr(
        user, "profile_pic_url", None
    )
    if not image_url:
        raise RuntimeError(f"No profile picture URL found for @{username}.")

    output_dir = Path(DOWNLOAD_DIR) / "dp"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{username}_dp.jpg"

    response = requests.get(
        str(image_url),
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.instagram.com/",
        },
        timeout=30,
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()
    extension = ".jpg"
    if "png" in content_type:
        extension = ".png"
    elif "webp" in content_type:
        extension = ".webp"
    output = output.with_suffix(extension)

    output.write_bytes(response.content)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("Downloaded profile picture is empty.")

    logger.info(
        "Instagram HD DP downloaded for @%s: %.2f MB",
        username,
        output.stat().st_size / (1024 ** 2),
    )
    return str(output)


def cleanup_video(video_path: str) -> None:
    video_file = Path(video_path)

    try:
        if video_file.exists():
            video_file.unlink()
            gc.collect()
            logger.info("🧹 Cleaned up %s", video_path)
    except Exception as e:
        logger.error("❌ Failed to clean up %s: %s", video_path, e)
