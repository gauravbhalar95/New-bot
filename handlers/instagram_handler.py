# handlers/instagram_handler.py

import gc
import logging
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Tuple

import yt_dlp

from config import DOWNLOAD_DIR, COOKIES_FILE
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging


logger = setup_logging(logging.DEBUG)

logger.add(
    "instagram_handler.log",
    rotation="10 MB",
    level="DEBUG"
)


SUPPORTED_DOMAINS = [
    "instagram.com"
]


Path(DOWNLOAD_DIR).mkdir(
    parents=True,
    exist_ok=True
)


def is_valid_url(url: str) -> bool:

    try:

        result = urlparse(url)

        return (
            result.scheme in ["http", "https"]
            and
            any(
                domain in result.netloc
                for domain in SUPPORTED_DOMAINS
            )
        )

    except ValueError:

        return False


def is_instagram_video(url: str) -> bool:

    return any(
        x in url
        for x in [
            "/reel/",
            "/tv/",
            "/video/"
        ]
    )


def download_progress_hook(d: dict) -> None:

    status = d.get("status")

    if status == "downloading":

        percent = d.get(
            "_percent_str",
            "0%"
        )

        speed = d.get(
            "_speed_str",
            "N/A"
        )

        eta = d.get(
            "_eta_str",
            "N/A"
        )

        logger.info(
            f"Downloading... "
            f"{percent} at {speed}, ETA: {eta}"
        )

    elif status == "finished":

        logger.info(
            f"✅ Download finished: "
            f"{d.get('filename')}"
        )


def process_instagram(
    url: str
) -> Tuple[Optional[str], int, Optional[str]]:

    url = url.split("#")[0]

    cookie_path = Path(
        COOKIES_FILE
    )

    if (
        not cookie_path.exists()
        or
        cookie_path.stat().st_size == 0
    ):

        logger.error(
            "❌ Instagram cookies file is missing or empty!"
        )

        return (
            None,
            0,
            "Instagram cookies file is missing or empty"
        )

    outtmpl = str(
        Path(DOWNLOAD_DIR)
        /
        "%(uploader)s - %(title)s.%(ext)s"
    )

    ydl_opts = {

        "format": "best",

        "merge_output_format": "mp4",

        "outtmpl": outtmpl,

        "socket_timeout": 10,

        "retries": 5,

        "progress_hooks": [
            download_progress_hook
        ],

        "cookiefile": str(
            cookie_path
        ),

        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ],

        "http_headers": {

            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; "
                "rv:123.0 Gecko/20100101 Firefox/123.0"
            ),

            "Accept-Language": (
                "en-US,en;q=0.9"
            ),

            "Referer": (
                "https://www.instagram.com/"
            ),
        },
    }

    try:

        with yt_dlp.YoutubeDL(
            ydl_opts
        ) as ydl:

            info_dict = ydl.extract_info(
                url,
                download=True
            )

        if not info_dict:

            return (
                None,
                0,
                "❌ Failed to extract info"
            )

        uploader = (
            info_dict.get("uploader")
            or
            info_dict.get("uploader_id")
            or
            "instagram"
        )

        title = (
            info_dict.get("title")
            or
            info_dict.get("id")
            or
            "video"
        )

        ext = (
            info_dict.get("ext")
            or
            "mp4"
        )

        raw_name = (
            f"{uploader} - "
            f"{title}.{ext}"
        )

        safe_name = sanitize_filename(
            raw_name
        )

        video_path = (
            Path(DOWNLOAD_DIR)
            /
            safe_name
        )

        if not video_path.exists():

            candidates = sorted(
                Path(DOWNLOAD_DIR).glob(
                    f"*{info_dict.get('id', '')}*"
                ),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            if candidates:

                video_path = candidates[0]

        file_size = (
            info_dict.get("filesize")
            or
            (
                video_path.stat().st_size
                if video_path.exists()
                else 0
            )
        )

        return (
            str(video_path),
            int(file_size),
            None
        )

    except yt_dlp.utils.DownloadError as e:

        logger.error(
            f"❌ Instagram download error: {e}"
        )

        return (
            None,
            0,
            str(e)
        )

    except Exception as e:

        logger.exception(
            "⚠️ Unexpected error downloading "
            f"Instagram video: {e}"
        )

        return (
            None,
            0,
            str(e)
        )


def cleanup_video(
    video_path: str
) -> None:

    video_file = Path(
        video_path
    )

    try:

        if video_file.exists():

            video_file.unlink()

            gc.collect()

            logger.info(
                f"🧹 Cleaned up {video_path}"
            )

    except Exception as e:

        logger.error(
            f"❌ Failed to clean up "
            f"{video_path}: {e}"
        )