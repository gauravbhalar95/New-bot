import logging
import gc
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from config import DOWNLOAD_DIR, FACEBOOK_FILE
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging


logger = setup_logging(logging.DEBUG)

logger.add(
    "facebook_handler.log",
    rotation="10 MB",
    level="DEBUG"
)


SUPPORTED_DOMAINS = [
    "facebook.com"
]


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


def is_facebook_video(url: str) -> bool:

    return any(
        x in url
        for x in [
            "/watch/",
            "/video/"
        ]
    )


def download_progress_hook(d: dict) -> None:

    if d.get("status") == "downloading":

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

    elif d.get("status") == "finished":

        logger.info(
            f"✅ Download finished: "
            f"{d.get('filename')}"
        )


def process_facebook(
    url: str
) -> tuple[str | None, int, str | None]:

    url = url.split("#")[0]

    cookie_path = Path(
        FACEBOOK_FILE
    )

    if (
        not cookie_path.exists()
        or
        cookie_path.stat().st_size == 0
    ):

        logger.error(
            "❌ Facebook cookies file is missing or empty!"
        )

        return (
            None,
            0,
            "Facebook cookies file is missing or empty"
        )

    ydl_opts = {

        "format": "bv+ba/b",

        "merge_output_format": "mp4",

        "outtmpl": str(
            Path(DOWNLOAD_DIR)
            /
            "%(title)s.%(ext)s"
        ),

        "socket_timeout": 10,

        "retries": 5,

        "compat_opts": [
            "facebook:login_all"
        ],

        "force_generic_extractor": True,

        "progress_hooks": [
            download_progress_hook
        ],

        "verbose": True,

        "cookiefile": str(
            cookie_path
        ),

        "extractor_args": {

            "facebook:ap_user": [
                "1"
            ],

            "facebook:viewport_width": [
                "1920"
            ],
        },

        "http_headers": {

            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; "
                "rv:123.0) Gecko/20100101 Firefox/123.0"
            ),

            "Accept-Language": (
                "en-US,en;q=0.9"
            ),

            "Referer": (
                "https://www.facebook.com/"
            ),

            "Sec-Fetch-Site": "same-origin",

            "Sec-Fetch-Mode": "navigate",

            "Sec-Fetch-Dest": "document"
        },

        "postprocessors": [

            {
                "key": "FFmpegVideoConvertor",

                "preferedformat": "mp4",
            }
        ],
    }

    try:

        with yt_dlp.YoutubeDL(
            ydl_opts
        ) as ydl:

            info_dict = ydl.extract_info(
                url,
                download=True
            )

            if info_dict:

                video_path = Path(
                    ydl.prepare_filename(
                        info_dict
                    )
                )

                file_size = (
                    info_dict.get(
                        "filesize"
                    )
                    or
                    (
                        video_path.stat().st_size
                        if video_path.exists()
                        else 0
                    )
                )

                if not video_path.exists():

                    mp4_path = (
                        video_path.with_suffix(
                            ".mp4"
                        )
                    )

                    if mp4_path.exists():

                        video_path = mp4_path

                return (
                    str(video_path),
                    file_size,
                    None
                )

            return (
                None,
                0,
                "❌ Failed to extract info"
            )

    except yt_dlp.utils.DownloadError as e:

        logger.error(
            f"❌ Facebook download error: {e}"
        )

        return (
            None,
            0,
            str(e)
        )

    except Exception as e:

        logger.error(
            f"⚠️ Unexpected error downloading "
            f"Facebook video: {e}"
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