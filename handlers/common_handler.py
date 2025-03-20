import os
import asyncio
import yt_dlp
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from utils.logger import setup_logging
from utils.sanitize import sanitize_filename
from utils.renamer import rename_file
from utils.thumb_generator import generate_thumbnail
from utils.file_server import get_direct_download_link
from config import DOWNLOAD_DIR, TELEGRAM_FILE_LIMIT
from flask import current_app

# Initialize logger
logger = setup_logging(logging.DEBUG)

async def compress_video(input_file, output_file):
    """Compress video to reduce file size using FFmpeg."""
    cmd = [
        "ffmpeg", "-i", input_file,
        "-c:v", "libx264", "-crf", "23", "-preset", "medium",
        "-c:a", "aac", "-b:a", "128k",
        output_file
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=300)  # 5-minute timeout
        if process.returncode == 0:
            logger.info(f"✅ Video compressed successfully: {output_file}")
            return output_file
        else:
            logger.error(f"❌ Compression failed: {stderr.decode().strip()}")
            return None
    except asyncio.TimeoutError:
        logger.error("❌ FFmpeg compression timed out.")
        process.kill()
        return None

@asynccontextmanager
async def yt_dlp_context(ydl_opts):
    """Context manager for yt-dlp instance."""
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        yield ydl

async def process_adult(url):
    """Download adult video asynchronously using yt-dlp."""
    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)

    file_path = None  # Initialize to avoid 'referenced before assignment' error

    ydl_opts = {
        'format': 'bestvideo[height<=480]/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title)s")}.%(ext)s',
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'continuedl': True,
        'http_chunk_size': 1048576,  # 1 MB chunk size
        'nocheckcertificate': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        },
        'logger': logger
    }

    try:
        async with yt_dlp_context(ydl_opts) as ydl:
            info_dict = await asyncio.to_thread(ydl.extract_info, url, download=True)
            if not info_dict:
                logger.error("❌ No info_dict returned. Download failed.")
                return None, 0, None

            file_path = Path(ydl.prepare_filename(info_dict))

            if not file_path.exists():
                logger.error("❌ Downloaded file not found.")
                return None, 0, None

            sanitized_filename = sanitize_filename(file_path.name)
            new_path = file_path.parent / sanitized_filename
            await rename_file(str(file_path), str(new_path))
            file_path = new_path  

            file_size = file_path.stat().st_size
            logger.info(f"✅ File Size: {file_size / (1024 * 1024):.2f} MB")

            thumbnail_path = await generate_thumbnail(str(file_path))
            if thumbnail_path:
                logger.info(f"✅ Thumbnail generated: {thumbnail_path}")
            else:
                logger.warning("⚠️ Thumbnail generation failed.")

            # Handle large files
            if file_size > TELEGRAM_FILE_LIMIT:
                logger.info("⚠️ File too large for Telegram. Compressing video...")

                compressed_file_path = file_path.with_stem(f"{file_path.stem}_compressed")
                compressed_file = await compress_video(str(file_path), str(compressed_file_path))

                if compressed_file:
                    compressed_size = Path(compressed_file).stat().st_size
                    if compressed_size < TELEGRAM_FILE_LIMIT:
                        logger.info(f"✅ Compressed file within limit: {compressed_file}")
                        return compressed_file, compressed_size, thumbnail_path

                logger.warning("⚠️ Compression failed or file still too large. Generating download link...")

                try:
                    with current_app.app_context():
                        download_link = get_direct_download_link(str(file_path))
                    if download_link:
                        logger.info(f"✅ Direct download link generated: {download_link}")
                        return None, file_size, download_link
                    else:
                        logger.error("❌ Direct download link generation failed.")
                        return None, file_size, None
                except Exception as e:
                    logger.error(f"⚠️ Error generating download link: {e}")
                    return None, file_size, None

            return str(file_path), file_size, thumbnail_path

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")
    except OSError as e:
        logger.error(f"❌ File system error: {e}")
    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")

    # Cleanup incomplete files to save disk space
    if file_path and file_path.exists():
        file_size = file_path.stat().st_size
        if file_size == 0:
            file_path.unlink()
            logger.info(f"🧹 Removed incomplete file: {file_path}")

    return None, 0, None