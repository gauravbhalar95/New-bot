import gc
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from config import DOWNLOAD_DIR
from utils.logger import setup_logging
from utils.renamer import get_file_extension, rename_file
from utils.sanitize import sanitize_filename

logger = setup_logging(logging.DEBUG)
if hasattr(logger, "add"):
    logger.add("instagram_handler.log", rotation="10 MB", level="DEBUG")

SUPPORTED_DOMAINS = ("instagram.com", "ddinstagram.com")


def is_valid_url(url: str) -> bool:
    """Return whether URL points to a supported Instagram domain."""
    try:
        result = urlparse(url)
        host = (result.hostname or "").lower()
        return result.scheme in ("http", "https") and any(
            host == domain or host.endswith("." + domain)
            for domain in SUPPORTED_DOMAINS
        )
    except ValueError:
        return False


def is_instagram_video(url: str) -> bool:
    """Identify common Instagram video/post URLs."""
    return any(part in url for part in ("/reel/", "/reels/", "/tv/", "/video/", "/p/"))


def download_progress_hook(data: dict) -> None:
    """Log yt-dlp download progress."""
    if data.get("status") == "downloading":
        logger.info(
            "Downloading Instagram media: %s at %s, ETA %s",
            data.get("_percent_str", "0%"),
            data.get("_speed_str", "N/A"),
            data.get("_eta_str", "N/A"),
        )
    elif data.get("status") == "finished":
        logger.info("Instagram download finished: %s", data.get("filename"))


def _rename_downloaded_video(downloaded_file: Path, info_dict: dict) -> str:
    """Rename a downloaded file with the creator name and safe title."""
    ext = get_file_extension(str(downloaded_file)) or downloaded_file.suffix or ".mp4"
    if not ext.startswith("."):
        ext = "." + ext

    title = str(info_dict.get("title") or info_dict.get("id") or "media").strip()
    media_id = info_dict.get("id") or "media"
    uploader_id = str(info_dict.get("uploader_id") or "").strip()
    candidates = (
        info_dict.get("creator"),
        info_dict.get("uploader"),
        info_dict.get("channel"),
        info_dict.get("channel_id"),
    )
    uploader = next(
        (str(value).strip() for value in candidates
         if value and not str(value).strip().isdigit()),
        "",
    )
    if not uploader:
        match = re.search(
            r"\b(?:video|reel|photo)\s+by\s+@?([A-Za-z0-9._]+)",
            title,
            flags=re.IGNORECASE,
        )
        if match:
            uploader = match.group(1)
    if not uploader and uploader_id and not uploader_id.isdigit():
        uploader = uploader_id
    uploader = uploader or "Instagram"

    safe_name = sanitize_filename(f"{uploader} - {title}{ext}")
    if not safe_name.lower().endswith(ext.lower()):
        safe_name = f"{Path(safe_name).stem}{ext}"
    if not Path(safe_name).stem.strip(" ._"):
        safe_name = sanitize_filename(f"Instagram_{media_id}{ext}")

    destination = downloaded_file.parent / safe_name
    counter = 1
    while destination.exists() and destination != downloaded_file:
        destination = downloaded_file.parent / f"{Path(safe_name).stem}_{counter}{ext}"
        counter += 1
    if destination != downloaded_file:
        rename_file(str(downloaded_file), str(destination))
    return str(destination if destination.exists() else downloaded_file)


def _try_instagram_post_images(url: str) -> list[str]:
    """Try Instaloader for image posts/carousels; import it only on demand."""
    from utils.instaloader_downloader import download_instagram_post

    paths = download_instagram_post(url)
    valid_paths = [str(path) for path in paths if Path(path).is_file() and Path(path).stat().st_size]
    if valid_paths:
        logger.info("Downloaded %d Instagram post media item(s)", len(valid_paths))
        return valid_paths
    return []


def _try_gallery_dl_images(url: str) -> list[str]:
    """Fallback Instagram downloader using gallery-dl, without Instaloader."""
    import shutil
    import subprocess
    import sys
    import tempfile

    output_root = Path(DOWNLOAD_DIR)
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gallery_dl_instagram_") as temp_dir:
        command = [
            sys.executable, "-m", "gallery_dl",
            "--dest", temp_dir,
        ]
        command.append(url)
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=180, check=False
        )
        downloaded = sorted(
            path for path in Path(temp_dir).rglob("*")
            if path.is_file()
            and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".avif", ".mp4"}
            and path.stat().st_size > 0
        )
        if result.returncode != 0 and not downloaded:
            detail = (result.stderr or result.stdout or "gallery-dl failed").strip()
            logger.warning("gallery-dl Instagram fallback failed: %s", detail[-1200:])
            return []

        paths = []
        for index, source in enumerate(downloaded, start=1):
            name = sanitize_filename(source.name) or f"instagram_{index}{source.suffix.lower()}"
            destination = output_root / name
            counter = 1
            while destination.exists():
                destination = output_root / f"{source.stem}_{counter}{source.suffix.lower()}"
                counter += 1
            shutil.copy2(source, destination)
            if destination.is_file() and destination.stat().st_size > 0:
                paths.append(str(destination))
        if paths:
            logger.info("gallery-dl downloaded %d Instagram media item(s)", len(paths))
        return paths


def process_instagram(url: str) -> str | list[str]:
    """Download an Instagram image/carousel or video. Heavy dependencies load on demand."""
    url = url.split("#", 1)[0].strip()
    if not is_valid_url(url):
        raise ValueError("Please provide a valid Instagram URL.")

    # If the URL explicitly points to an image/carousel (for example
    # ?img_index=2), try gallery-dl first, then Instaloader. Reels/videos
    # and ordinary post URLs go to yt-dlp first.
    is_post_url = bool(re.search(r"/p/[^/?#]+", url, flags=re.IGNORECASE))
    has_image_hint = bool(re.search(r"(?:img|image)", url, flags=re.IGNORECASE))

    if is_post_url and has_image_hint:
        try:
            image_paths = _try_gallery_dl_images(url)
            if image_paths:
                return image_paths
        except Exception as exc:
            logger.warning("gallery-dl image-first attempt failed; trying Instaloader: %s", exc)
        try:
            image_paths = _try_instagram_post_images(url)
            if image_paths:
                return image_paths
        except Exception as exc:
            logger.warning("Instaloader image fallback failed; trying yt-dlp: %s", exc)

    # Import yt-dlp and cookie refresh code only when a download is requested.
    import yt_dlp

    download_dir = Path(DOWNLOAD_DIR)
    download_dir.mkdir(parents=True, exist_ok=True)
    ydl_opts = {
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(download_dir / "ig_%(id)s.%(ext)s"),
        "restrictfilenames": True,
        "socket_timeout": 15,
        "retries": 5,
        "progress_hooks": [download_progress_hook],
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) "
                "Gecko/20100101 Firefox/123.0"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.instagram.com/",
        },
        "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
    }

    # Public-only mode: do not load cookies or trigger a login/session refresh.
    # Automated logins can trigger Instagram security checkpoints or email-change prompts.
    logger.info("Attempting Instagram download without account cookies (public access only).")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise RuntimeError("Instagram returned no media information.")
            if info.get("entries"):
                info = next((entry for entry in info["entries"] if entry), info)

            raw_path = Path(ydl.prepare_filename(info))
            mp4_path = raw_path.with_suffix(".mp4")
            downloaded_file = mp4_path if mp4_path.exists() else raw_path
            if not downloaded_file.is_file():
                raise FileNotFoundError(f"Downloaded Instagram file not found: {raw_path}")

            final_path = _rename_downloaded_video(downloaded_file, info)
            logger.info("Instagram media ready: %s", final_path)
            return final_path
    except Exception as exc:
        # yt-dlp can fail with "No video formats found" for image posts and
        # carousels. Try gallery-dl after the primary attempt, then Instaloader
        # for /p/ posts. Keep the original yt-dlp-first behavior for reels/videos.
        logger.warning("Instagram yt-dlp attempt failed: %s", exc)

        try:
            fallback_paths = _try_gallery_dl_images(url)
            if fallback_paths:
                logger.info(
                    "Instagram fallback succeeded with gallery-dl (%d file(s))",
                    len(fallback_paths),
                )
                return fallback_paths
        except Exception as fallback_exc:
            logger.warning("Instagram gallery-dl fallback failed: %s", fallback_exc)

        if is_post_url:
            try:
                fallback_paths = _try_instagram_post_images(url)
                if fallback_paths:
                    logger.info(
                        "Instagram fallback succeeded with Instaloader (%d file(s))",
                        len(fallback_paths),
                    )
                    return fallback_paths
            except Exception as fallback_exc:
                logger.warning("Instagram Instaloader fallback failed: %s", fallback_exc)

        # Preserve the real primary error so the caller can report failure.
        raise


async def send_video_to_user(bot, chat_id: int, video_path: str) -> None:
    """Send one downloaded video to a Telegram user."""
    try:
        with open(video_path, "rb") as video:
            await bot.send_video(chat_id, video, caption=Path(video_path).name)
    except Exception:
        logger.exception("Failed to send Instagram video to chat %s", chat_id)


def cleanup_video(video_path: str) -> None:
    """Delete a downloaded file after it has been sent."""
    if not video_path:
        return
    try:
        Path(video_path).unlink(missing_ok=True)
        gc.collect()
    except Exception:
        logger.exception("Failed to clean up Instagram file: %s", video_path)
