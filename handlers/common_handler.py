import os
import asyncio
import yt_dlp
import logging
from utils.logger import setup_logging
from utils.thumb_generator import generate_thumbnail
from utils.sanitize import sanitize_filename
from utils.renamer import rename_file
from utils.file_server import get_direct_download_link
from config import DOWNLOAD_DIR, TELEGRAM_FILE_LIMIT
from flask import current_app
import subprocess

# Initialize logger
logger = setup_logging(logging.DEBUG)

# ✅ Improved Compression Function
async def compress_video(input_file, output_file):
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

    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        logger.info(f"✅ Video compressed successfully: {output_file}")
        return output_file
    else:
        logger.error(f"❌ Compression failed: {stderr.decode().strip()}")
        return None

async def process_adult(url):
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'best',
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'continuedl': True,
        'http_chunk_size': 1048576,  # 1 MB chunk size
        'quiet': False,
        'nocheckcertificate': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }
    }

    try:
        loop = asyncio.get_running_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await loop.run_in_executor(None, ydl.extract_info, url, True)
            if not info_dict or "requested_downloads" not in info_dict:
                logger.error("❌ No video found.")
                return None, None, None

            file_path = info_dict["requested_downloads"][0]["filepath"]

            if not os.path.exists(file_path):
                logger.error("❌ Downloaded file not found.")
                return None, None, None

            sanitized_filename = await sanitize_filename(os.path.basename(file_path))
            new_path = os.path.join(DOWNLOAD_DIR, sanitized_filename)

            await rename_file(file_path, new_path)
            file_path = new_path  

            file_size = os.path.getsize(file_path) / (1024 * 1024)  # Convert to MB
            logger.info(f"✅ File Size: {file_size:.2f} MB")

            # ✅ Await async function & check for None
            thumbnail_path = await generate_thumbnail(file_path)

            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"✅ Thumbnail generated: {thumbnail_path}")
            else:
                logger.warning("⚠️ Thumbnail generation failed.")

            logger.info(f"✅ Download completed: {file_path}")

            # ✅ Handle large files
            if file_size > TELEGRAM_FILE_LIMIT / (1024 * 1024):  # Convert TELEGRAM_FILE_LIMIT to MB
                logger.info("⚠️ File too large for Telegram. Compressing video...")

                compressed_file_path = file_path.replace(".mp4", "_compressed.mp4")
                compressed_file = await compress_video(file_path, compressed_file_path)

                if compressed_file and os.path.getsize(compressed_file) < TELEGRAM_FILE_LIMIT:
                    logger.info(f"✅ Compressed file within limit: {compressed_file}")
                    return compressed_file, os.path.getsize(compressed_file), thumbnail_path
                else:
                    logger.warning("⚠️ Compression failed or file still too large. Generating download link...")

                    with current_app.app_context():
                        download_link = get_direct_download_link(file_path)

                    if download_link:
                        logger.info(f"✅ Direct download link generated: {download_link}")
                        return None, file_size, download_link
                    else:
                        logger.error("❌ Direct download link generation failed.")
                        return None, file_size, None

            return file_path, file_size, thumbnail_path

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ Download failed: {e}")
    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")

    return None, None, None