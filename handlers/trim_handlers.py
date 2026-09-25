import os
import yt_dlp
import logging
import subprocess
import platform
import shutil
import urllib.request
import zipfile

from config import DOWNLOAD_DIR, YOUTUBE_FILE
from utils.logger import setup_logging

# Setup logging
logger = setup_logging(logging.DEBUG)

# Ensure the download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def _ensure_deno():
    """Return a usable Deno executable for yt-dlp EJS challenge solving."""
    existing = shutil.which("deno")
    if existing:
        return existing
    bin_dir = os.path.join(DOWNLOAD_DIR, ".bin")
    deno_path = os.path.join(bin_dir, "deno")
    if os.path.isfile(deno_path) and os.access(deno_path, os.X_OK):
        return deno_path
    os.makedirs(bin_dir, exist_ok=True)
    machine = platform.machine().lower()
    asset = (
        "deno-aarch64-unknown-linux-gnu.zip"
        if machine in ("aarch64", "arm64")
        else "deno-x86_64-unknown-linux-gnu.zip"
    )
    archive = os.path.join(bin_dir, "deno.zip")
    url = "https://github.com/denoland/deno/releases/latest/download/" + asset
    logger.info("Installing Deno for yt-dlp EJS challenge solving...")
    urllib.request.urlretrieve(url, archive)
    with zipfile.ZipFile(archive) as zf:
        zf.extract("deno", bin_dir)
    os.remove(archive)
    os.chmod(deno_path, 0o755)
    return deno_path


def time_to_seconds(time_str):
    """
    Converts time string to seconds.
    Supports HH:MM:SS, MM:SS, and SS formats.
    """
    try:
        parts = time_str.split(":")

        if len(parts) == 3:
            h, m, s = map(int, parts)
            return h * 3600 + m * 60 + s

        elif len(parts) == 2:
            m, s = map(int, parts)
            return m * 60 + s

        elif len(parts) == 1:
            return int(parts[0])

        else:
            logger.error(f"Invalid time format: {time_str}")
            return None

    except ValueError as e:
        logger.error(f"Time conversion error for '{time_str}': {e}")
        return None


def download_media(url, is_audio=False):
    """
    Downloads video or audio using yt-dlp.

    Returns:
        str: Path to downloaded file or None
    """

    output_path = os.path.join(
        DOWNLOAD_DIR,
        "%(title)s_%(id)s.%(ext)s"
    )

    cookie_file = YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None

    try:
        deno_path = _ensure_deno()
        logger.info("Using Deno for yt-dlp EJS: %s", deno_path)
    except Exception as e:
        logger.warning("Could not install Deno: %s", e)
        deno_path = None

    base_opts = {
        "outtmpl": output_path,
        "cookiefile": cookie_file,
        "quiet": False,
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 5,
        "fragment_retries": 5,
        "remote_components": ["ejs:github"],
        "js_runtimes": {"deno": {"path": deno_path}} if deno_path else {},
    }

    if is_audio:
        base_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        base_opts.update({
            "format": "bestvideo*+bestaudio/best",
            "merge_output_format": "mp4",
        })

    client_attempts = [None, ["android_vr"], ["web_embedded"]]
    last_error = None

    for player_clients in client_attempts:
        ydl_opts = dict(base_opts)
        if player_clients:
            ydl_opts["extractor_args"] = {
                "youtube": {"player_client": player_clients}
            }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

            if not info:
                return None

            file_path = ydl.prepare_filename(info)

            if is_audio:
                file_path = file_path.rsplit(".", 1)[0] + ".mp3"

            else:
                mp4_path = file_path.rsplit(".", 1)[0] + ".mp4"

                if os.path.exists(mp4_path):
                    file_path = mp4_path

                elif not os.path.exists(file_path):
                    base_name = file_path.rsplit(".", 1)[0]

                    for file in os.listdir(DOWNLOAD_DIR):
                        if file.startswith(os.path.basename(base_name)):
                            file_path = os.path.join(
                                DOWNLOAD_DIR,
                                file
                            )
                            break

                logger.debug(f"Downloaded file path: {file_path}")

                return file_path if os.path.exists(file_path) else None

        except yt_dlp.utils.DownloadError as e:
            last_error = e
            logger.warning("YouTube trim download attempt failed: %s", e, exc_info=True)
            continue
        except Exception as e:
            last_error = e
            logger.warning("Unexpected trim download error: %s", e, exc_info=True)
            continue

    logger.error("All YouTube trim download attempts failed: %s", last_error)
    return None


def trim_video(input_path, start_time, end_time):
    """
    Trims a video file using FFmpeg.

    Returns:
        tuple: (file_path, file_size)
    """

    if not os.path.exists(input_path):
        logger.error(f"Input file does not exist: {input_path}")
        return None, None

    output_path = (
        input_path.rsplit(".", 1)[0]
        + f"_trim_{start_time}_{end_time}.mp4"
    )

    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.error("FFmpeg not found. Please install FFmpeg.")
        return None, None

    command = [
        "ffmpeg",
        "-i", input_path,
        "-ss", str(start_time),
        "-to", str(end_time),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-preset", "fast",
        "-y",
        output_path
    ]

    logger.debug(
        f"Running FFmpeg video trim command: {' '.join(command)}"
    )

    try:
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if process.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)

            logger.info(
                f"Video trimming successful. "
                f"Output file: {output_path}, "
                f"Size: {file_size} bytes"
            )

            return output_path, file_size

        logger.error(
            f"FFmpeg video trim error "
            f"(return code {process.returncode}): "
            f"{process.stderr}"
        )

        return trim_video_alternative(
            input_path,
            start_time,
            end_time
        )

    except Exception as e:
        logger.error(
            f"Exception during video trim: {str(e)}",
            exc_info=True
        )
        return None, None


def trim_video_alternative(input_path, start_time, end_time):
    """
    Alternative video trimming method using stream copy.
    """

    output_path = (
        input_path.rsplit(".", 1)[0]
        + f"_trim_alt_{start_time}_{end_time}.mp4"
    )

    command = [
        "ffmpeg",
        "-ss", str(start_time),
        "-i", input_path,
        "-t", str(end_time - start_time),
        "-c", "copy",
        "-y",
        output_path
    ]

    logger.debug(
        f"Running alternative FFmpeg video trim command: "
        f"{' '.join(command)}"
    )

    try:
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if process.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)

            logger.info(
                f"Alternative video trimming successful. "
                f"Output file: {output_path}, "
                f"Size: {file_size} bytes"
            )

            return output_path, file_size

        logger.error(
            f"Alternative FFmpeg video trim error "
            f"(return code {process.returncode}): "
            f"{process.stderr}"
        )

        return None, None

    except Exception as e:
        logger.error(
            f"Exception during alternative video trim: {str(e)}",
            exc_info=True
        )
        return None, None


def trim_audio(input_path, start_time, end_time):
    """
    Trims an audio file using FFmpeg.

    Returns:
        tuple: (file_path, file_size)
    """

    if not os.path.exists(input_path):
        logger.error(f"Input file does not exist: {input_path}")
        return None, None

    output_path = (
        input_path.rsplit(".", 1)[0]
        + f"_trim_{start_time}_{end_time}.mp3"
    )

    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.error("FFmpeg not found. Please install FFmpeg.")
        return None, None

    command = [
        "ffmpeg",
        "-i", input_path,
        "-ss", str(start_time),
        "-to", str(end_time),
        "-acodec", "libmp3lame",
        "-q:a", "2",
        "-y",
        output_path
    ]

    logger.debug(
        f"Running FFmpeg audio trim command: {' '.join(command)}"
    )

    try:
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if process.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)

            logger.info(
                f"Audio trimming successful. "
                f"Output file: {output_path}, "
                f"Size: {file_size} bytes"
            )

            return output_path, file_size

        logger.error(
            f"FFmpeg audio trim error "
            f"(return code {process.returncode}): "
            f"{process.stderr}"
        )

        return trim_audio_alternative(
            input_path,
            start_time,
            end_time
        )

    except Exception as e:
        logger.error(
            f"Exception during audio trim: {str(e)}",
            exc_info=True
        )
        return None, None


def trim_audio_alternative(input_path, start_time, end_time):
    """
    Alternative audio trimming method using stream copy.
    """

    output_path = (
        input_path.rsplit(".", 1)[0]
        + f"_trim_alt_{start_time}_{end_time}.mp3"
    )

    command = [
        "ffmpeg",
        "-ss", str(start_time),
        "-i", input_path,
        "-t", str(end_time - start_time),
        "-acodec", "copy",
        "-y",
        output_path
    ]

    logger.debug(
        f"Running alternative FFmpeg audio trim command: "
        f"{' '.join(command)}"
    )

    try:
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if process.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)

            logger.info(
                f"Alternative audio trimming successful. "
                f"Output file: {output_path}, "
                f"Size: {file_size} bytes"
            )

            return output_path, file_size

        logger.error(
            f"Alternative FFmpeg audio trim error "
            f"(return code {process.returncode}): "
            f"{process.stderr}"
        )

        return None, None

    except Exception as e:
        logger.error(
            f"Exception during alternative audio trim: {str(e)}",
            exc_info=True
        )
        return None, None


def process_video_trim(url, start_time, end_time):
    """
    Downloads video and trims it.
    """

    try:
        start_seconds = (
            time_to_seconds(start_time)
            if isinstance(start_time, str)
            else start_time
        )

        end_seconds = (
            time_to_seconds(end_time)
            if isinstance(end_time, str)
            else end_time
        )

        logger.debug(
            f"Time conversion results - "
            f"start_time: '{start_time}' → {start_seconds}s, "
            f"end_time: '{end_time}' → {end_seconds}s"
        )

        if start_seconds is None or end_seconds is None:
            logger.error("Invalid time format for video trim")
            return None, None

        if start_seconds >= end_seconds:
            logger.error(
                f"Invalid video trim range: "
                f"Start time ({start_seconds}s) must be less than "
                f"end time ({end_seconds}s)"
            )
            return None, None

        logger.info(f"Downloading video for trimming from: {url}")

        video_path = download_media(
            url,
            is_audio=False
        )

        if not video_path:
            logger.error("Failed to download video for trimming")
            return None, None

        orig_size = os.path.getsize(video_path)

        logger.info(
            f"Downloaded video file: {video_path}, "
            f"Size: {orig_size} bytes"
        )

        logger.info(
            f"Trimming video: "
            f"Start: {start_seconds}s, "
            f"End: {end_seconds}s"
        )

        trimmed_path, file_size = trim_video(
            video_path,
            start_seconds,
            end_seconds
        )

        try:
            os.remove(video_path)
            logger.info(
                f"Removed original video file: {video_path}"
            )
        except Exception as e:
            logger.warning(
                f"Could not remove original video file "
                f"{video_path}: {e}"
            )

        if trimmed_path:
            return trimmed_path, file_size

        logger.error("Failed to trim video")
        return None, None

    except Exception as e:
        logger.error(
            f"Error in process_video_trim: {e}",
            exc_info=True
        )
        return None, None


def process_audio_trim(url, start_time, end_time):
    """
    Downloads audio and trims it.
    """

    try:
        start_seconds = (
            time_to_seconds(start_time)
            if isinstance(start_time, str)
            else start_time
        )

        end_seconds = (
            time_to_seconds(end_time)
            if isinstance(end_time, str)
            else end_time
        )

        logger.debug(
            f"Time conversion results - "
            f"start_time: '{start_time}' → {start_seconds}s, "
            f"end_time: '{end_time}' → {end_seconds}s"
        )

        if start_seconds is None or end_seconds is None:
            logger.error("Invalid time format for audio trim")
            return None, None

        if start_seconds >= end_seconds:
            logger.error(
                f"Invalid audio trim range: "
                f"Start time ({start_seconds}s) must be less than "
                f"end time ({end_seconds}s)"
            )
            return None, None

        logger.info(f"Downloading audio for trimming from: {url}")

        audio_path = download_media(
            url,
            is_audio=True
        )

        if not audio_path:
            logger.error("Failed to download audio for trimming")
            return None, None

        orig_size = os.path.getsize(audio_path)

        logger.info(
            f"Downloaded audio file: {audio_path}, "
            f"Size: {orig_size} bytes"
        )

        logger.info(
            f"Trimming audio: "
            f"Start: {start_seconds}s, "
            f"End: {end_seconds}s"
        )

        trimmed_path, file_size = trim_audio(
            audio_path,
            start_seconds,
            end_seconds
        )

        try:
            os.remove(audio_path)
            logger.info(
                f"Removed original audio file: {audio_path}"
            )
        except Exception as e:
            logger.warning(
                f"Could not remove original audio file "
                f"{audio_path}: {e}"
            )

        if trimmed_path:
            return trimmed_path, file_size

        logger.error("Failed to trim audio")
        return None, None

    except Exception as e:
        logger.error(
            f"Error in process_audio_trim: {e}",
            exc_info=True
        )
        return None, None