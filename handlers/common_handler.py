import os
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager

import yt_dlp

from utils.logger import setup_logging
from utils.sanitize import sanitize_filename
from utils.renamer import rename_file
from utils.thumb_generator import generate_thumbnail
from config import DOWNLOAD_DIR, TELEGRAM_FILE_LIMIT

# ------------------------------------------------------------------
# Logger
# ------------------------------------------------------------------
logger = setup_logging(logging.DEBUG)

# ------------------------------------------------------------------
# yt-dlp async context
# ------------------------------------------------------------------
@asynccontextmanager
async def yt_dlp_context(ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        yield ydl

# ------------------------------------------------------------------
# FFmpeg compression
# ------------------------------------------------------------------
async def compress_video(input_file: str, output_file: str):
    cmd = [
        "ffmpeg", "-y",
        "-i", input_file,
        "-c:v", "libx264",
        "-crf", "23",
        "-preset", "medium",
        "-c:a", "aac",
        "-b:a", "128k",
        output_file
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=300)

        if process.returncode == 0:
            logger.info(f"✅ Video compressed: {output_file}")
            return output_file
        else:
            logger.error(f"❌ Compression failed:\n{stderr.decode(errors='ignore')}")
    except asyncio.TimeoutError:
        logger.error("❌ Compression timeout, killing ffmpeg...")
        process.kill()

    return None

# ------------------------------------------------------------------
# MAIN ADULT HANDLER
# ------------------------------------------------------------------
async def process_adult(url: str):
    """
    Adult video handler (XHamster safe)
    Returns: (file_path, file_size, thumbnail_path)
    """

    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
    file_path = None

    ydl_opts = {
        # ✅ IMPORTANT: XHamster works best with this
        "format": "best",

        "outtmpl": f"{DOWNLOAD_DIR}/{sanitize_filename('%(title).100s')}.%(ext)s",
        "merge_output_format": "mp4",
        "noplaylist": True,

        # Network / stability
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "continuedl": True,

        # ❌ Do NOT ignore errors
        "ignoreerrors": False,

        # Anti-block
        "geo_bypass": True,
        "age_limit": 99,

        # Performance
        "concurrent_fragment_downloads": 2,

        # Logging
        "quiet": True,
        "no_warnings": True,
        "logger": logger,

        # SSL / routing
        "nocheckcertificate": True,
        "source_address": "0.0.0.0",

        "headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            "Referer": "https://xhamster.com"
        }
    }

    try:
        async with yt_dlp_context(ydl_opts) as ydl:

            # ----------------------------------------------------------
            # STEP 1: PROBE (NO DOWNLOAD)
            # ----------------------------------------------------------
            try:
                info = await asyncio.to_thread(
                    ydl.extract_info,
                    url,
                    download=False
                )
            except Exception as e:
                if "videoModel" in str(e):
                    logger.error("❌ XHamster extractor broken (videoModel).")
                    return None, 0, None
                logger.error(f"❌ Metadata extraction failed: {e}")
                return None, 0, None

            if not info:
                logger.error("❌ No metadata returned.")
                return None, 0, None

            # ----------------------------------------------------------
            # STEP 2: DOWNLOAD
            # ----------------------------------------------------------
            info = await asyncio.to_thread(
                ydl.extract_info,
                url,
                download=True
            )

            if not info:
                logger.error("❌ Download failed (no info_dict).")
                return None, 0, None

            file_path = Path(ydl.prepare_filename(info))

            # Fix extension mismatch
            if not file_path.exists():
                mp4_path = file_path.with_suffix(".mp4")
                if mp4_path.exists():
                    file_path = mp4_path
                else:
                    logger.error("❌ Downloaded file not found.")
                    return None, 0, None

            # ----------------------------------------------------------
            # Sanitize filename
            # ----------------------------------------------------------
            sanitized_name = sanitize_filename(file_path.name)
            new_path = file_path.parent / sanitized_name

            if file_path != new_path:
                await rename_file(str(file_path), str(new_path))
                file_path = new_path

            file_size = file_path.stat().st_size
            logger.info(f"✅ File size: {file_size / (1024 ** 2):.2f} MB")

            # ----------------------------------------------------------
            # Thumbnail
            # ----------------------------------------------------------
            thumbnail_path = await generate_thumbnail(str(file_path))

            # ----------------------------------------------------------
            # Telegram size handling
            # ----------------------------------------------------------
            if file_size > TELEGRAM_FILE_LIMIT:
                logger.warning("⚠️ File exceeds Telegram limit, compressing...")

                compressed_path = file_path.with_stem(
                    f"{file_path.stem}_compressed"
                )

                compressed = await compress_video(
                    str(file_path),
                    str(compressed_path)
                )

                if compressed:
                    new_size = Path(compressed).stat().st_size
                    if new_size < TELEGRAM_FILE_LIMIT:
                        logger.info("✅ Compression successful.")
                        return compressed, new_size, thumbnail_path

                logger.warning("⚠️ Still too large after compression.")
                return str(file_path), file_size, thumbnail_path

            return str(file_path), file_size, thumbnail_path

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ yt-dlp DownloadError: {e}")

    except OSError as e:
        logger.error(f"❌ Filesystem error: {e}")

    except Exception as e:
        logger.error(f"❌ Unexpected adult handler error: {e}")

    # Cleanup zero-byte file
    if file_path and file_path.exists() and file_path.stat().st_size == 0:
        file_path.unlink(missing_ok=True)
        logger.info("🧹 Removed zero-size file")

    return None, 0, None