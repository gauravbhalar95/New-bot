import os
import yt_dlp
import logging

from utils.sanitize import sanitize_filename
from config import YOUTUBE_FILE, DOWNLOAD_DIR
from utils.logger import setup_logging


# Initialize logger
logger = setup_logging(logging.DEBUG)


def process_youtube(url):
    """Download a YouTube video with format/client fallbacks."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    output_template = (
        f"{DOWNLOAD_DIR}/{sanitize_filename('%(title)s')}.%(ext)s"
    )

    # YouTube is currently rolling out PO-token/SABR enforcement.
    # Try a normal/default extraction first, then Safari/embedded clients.
    client_attempts = [
        None,
        ["web_safari", "web_embedded"],
    ]

    last_error = None

    for attempt, player_clients in enumerate(client_attempts, start=1):
        ydl_opts = {
            # More tolerant than the old hard-coded "bv+ba/b".
            "format": "bestvideo*+bestaudio/best",
            "outtmpl": output_template,
            "cookiefile": (
                YOUTUBE_FILE
                if os.path.exists(YOUTUBE_FILE)
                else None
            ),
            "socket_timeout": 20,
            "retries": 5,
            "fragment_retries": 5,
            "logger": logger,
            "verbose": True,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "ignoreerrors": False,
        }

        if player_clients:
            ydl_opts["extractor_args"] = {
                "youtube": {
                    "player_client": player_clients
                }
            }

        try:
            logger.info(
                f"▶️ YouTube attempt {attempt}/"
                f"{len(client_attempts)}"
                + (
                    f" using clients: {','.join(player_clients)}"
                    if player_clients
                    else " using default clients"
                )
            )

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)

                if not info_dict:
                    raise yt_dlp.utils.DownloadError(
                        "No video information returned"
                    )

                if (
                    "entries" in info_dict
                    and info_dict.get("entries") is not None
                    and not info_dict["entries"]
                ):
                    raise yt_dlp.utils.DownloadError(
                        "Video unavailable or restricted"
                    )

                # Prefer the actual final filepath reported by yt-dlp.
                candidates = []

                requested_downloads = (
                    info_dict.get("requested_downloads") or []
                )

                for item in requested_downloads:
                    path = item.get("filepath")
                    if path and os.path.isfile(path):
                        candidates.append(path)

                for key in ("_filename", "filename"):
                    path = info_dict.get(key)
                    if path and os.path.isfile(path):
                        candidates.append(path)

                prepared = ydl.prepare_filename(info_dict)
                candidates.extend([
                    prepared,
                    os.path.splitext(prepared)[0] + ".mp4",
                ])

                file_path = next(
                    (
                        path for path in candidates
                        if path and os.path.isfile(path)
                    ),
                    None,
                )

                if not file_path:
                    raise yt_dlp.utils.DownloadError(
                        "yt-dlp completed but the output file was not found"
                    )

                file_size = os.path.getsize(file_path)

                logger.info(
                    f"✅ YouTube download finished: {file_path} "
                    f"({file_size / (1024 ** 2):.2f} MB)"
                )

                return file_path, file_size, None

        except (
            yt_dlp.utils.ExtractorError,
            yt_dlp.utils.DownloadError,
        ) as e:
            last_error = e
            logger.warning(
                f"⚠️ YouTube attempt {attempt} failed: {e}"
            )

            if attempt < len(client_attempts):
                logger.info("🔄 Retrying YouTube with fallback client...")
                continue

            break

        except Exception as e:
            last_error = e
            logger.error(
                f"⚠️ Unexpected YouTube error: {e}",
                exc_info=True,
            )

            if attempt < len(client_attempts):
                continue

            break

    logger.error(f"❌ All YouTube download attempts failed: {last_error}")

    return (
        None,
        0,
        str(last_error) if last_error else "YouTube download failed.",
    )


def extract_audio_ffmpeg(url):
    """Download and extract audio from a YouTube video synchronously."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    audio_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{DOWNLOAD_DIR}/{sanitize_filename('%(title)s')}.%(ext)s",
        "cookiefile": YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }],
        "logger": logger,
        "verbose": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

            if not info_dict:
                logger.error(
                    "❌ No info_dict returned. Audio download failed."
                )
                return None, 0

            audio_filename = ydl.prepare_filename(info_dict)

            audio_filename = os.path.splitext(audio_filename)[0] + ".mp3"

            file_size = (
                os.path.getsize(audio_filename)
                if os.path.exists(audio_filename)
                else 0
            )

            return audio_filename, file_size

    except yt_dlp.utils.ExtractorError as e:
        logger.error(f"❌ Extractor Error: {e}")
        return None, 0

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ Download Error: {e}")
        return None, 0

    except Exception as e:
        logger.error(
            f"⚠️ Error extracting audio: {e}",
            exc_info=True
        )
        return None, 0