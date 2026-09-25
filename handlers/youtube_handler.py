import os
import yt_dlp
import logging
from utils.sanitize import sanitize_filename
from config import YOUTUBE_FILE, DOWNLOAD_DIR
from utils.logger import setup_logging


logger = setup_logging(logging.DEBUG)


def get_youtube_cookie_file():
    """Return a usable YouTube Netscape cookie file, if configured."""
    if not os.path.isfile(YOUTUBE_FILE):
        logger.warning(
            "⚠️ YouTube cookies are not configured. "
            "Set the Koyeb secret YOUTUBE_COOKIES_B64."
        )
        return None

    try:
        size = os.path.getsize(YOUTUBE_FILE)
        if size < 20:
            logger.warning("⚠️ YouTube cookie file is empty or too small.")
            return None

        with open(YOUTUBE_FILE, "rb") as cookie_fp:
            sample = cookie_fp.read(4096)

        # yt-dlp expects a Netscape/Mozilla cookies.txt file.
        text = sample.decode("utf-8", errors="ignore")
        has_cookie_header = (
            "# Netscape HTTP Cookie File" in text
            or "# HTTP Cookie File" in text
        )
        has_cookie_rows = any(
            len(line.split("\t")) >= 7
            for line in text.splitlines()
            if line and not line.startswith("#")
        )

        if not (has_cookie_header or has_cookie_rows):
            logger.warning(
                "⚠️ YouTube cookie file is not in Netscape cookies.txt format."
            )
            return None

        logger.info(
            "✅ YouTube cookie file loaded: %.1f KB",
            size / 1024,
        )
        return YOUTUBE_FILE

    except OSError as exc:
        logger.warning("⚠️ Could not read YouTube cookie file: %s", exc)
        return None


def process_youtube(url, quality=None):
    """Download a YouTube video with format/client fallbacks."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    output_template = f"{DOWNLOAD_DIR}/{sanitize_filename('%(title)s')}.%(ext)s"
    cookie_file = get_youtube_cookie_file()

    # Keep Python as the application runtime. Node.js is used only by yt-dlp
    # for YouTube's EJS JavaScript challenge solving.
    client_attempts = [
        None,
        ["web_embedded"],
    ]

    last_error = None

    if quality:
        quality = str(quality).lower().replace("p", "")
        if quality not in {"144", "240", "360", "480", "720", "1080", "1440", "2160"}:
            logger.warning("Invalid YouTube quality %s; using best", quality)
            quality = None

    for attempt, player_clients in enumerate(client_attempts, start=1):
        ydl_opts = {
            "format": (
                f"bestvideo[height<={quality}]+bestaudio/"
                f"best[height<={quality}]/best"
                if quality
                else "bestvideo*+bestaudio/best"
            ),
            "outtmpl": output_template,
            "cookiefile": cookie_file,
            "socket_timeout": 20,
            "retries": 5,
            "fragment_retries": 5,
            "logger": logger,
            "verbose": True,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "ignoreerrors": False,
            "js_runtimes": {
                "node": "/usr/bin/node",
            },
        }

        if player_clients:
            ydl_opts["extractor_args"] = {
                "youtube": {
                    "player_client": player_clients,
                }
            }

        try:
            logger.info(
                f"▶️ YouTube attempt {attempt}/{len(client_attempts)}"
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

                candidates = []
                requested_downloads = info_dict.get("requested_downloads") or []

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

        except (yt_dlp.utils.ExtractorError, yt_dlp.utils.DownloadError) as e:
            last_error = e
            logger.warning(
                f"⚠️ YouTube attempt {attempt} failed: {e}",
                exc_info=True,
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

    if last_error and "Sign in to confirm" in str(last_error):
        last_error = (
            "YouTube requires authentication. Configure a fresh "
            "YOUTUBE_COOKIES_B64 secret in Koyeb and redeploy."
        )

    return (
        None,
        0,
        str(last_error) if last_error else "YouTube download failed.",
    )


def extract_audio_ffmpeg(url):
    """Download and extract audio from a YouTube video synchronously."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    cookie_file = get_youtube_cookie_file()

    audio_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{DOWNLOAD_DIR}/{sanitize_filename('%(title)s')}.%(ext)s",
        "cookiefile": cookie_file,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }],
        "logger": logger,
        "verbose": True,
        "noplaylist": True,
        "js_runtimes": {
            "node": "/usr/bin/node",
        },
    }

    try:
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

            if not info_dict:
                logger.error("❌ No info_dict returned. Audio download failed.")
                return None, 0

            audio_filename = os.path.splitext(
                ydl.prepare_filename(info_dict)
            )[0] + ".mp3"

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
        logger.error(f"⚠️ Error extracting audio: {e}", exc_info=True)
        return None, 0
