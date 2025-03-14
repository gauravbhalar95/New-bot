import os
import asyncio
import yt_dlp
import logging
from utils.logger import setup_logging
from utils.thumb_generator import generate_thumbnail
from utils.sanitize import sanitize_filename  # Ensure this is async
from utils.renamer import rename_file
from utils.file_server import get_direct_download_link
from config import DOWNLOAD_DIR, TELEGRAM_FILE_LIMIT
from your_flask_app import app  # Import your Flask app instance

# Initialize logger
logger = setup_logging(logging.DEBUG)

async def process_adult(url):
    """
    Downloads a video and returns (file_path, file_size, thumbnail_path).
    """
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

            # ✅ Await sanitize_filename to ensure async handling
            sanitized_filename = await sanitize_filename(os.path.basename(file_path))
            new_path = os.path.join(DOWNLOAD_DIR, sanitized_filename)

            await rename_file(file_path, new_path)  # ✅ Await added
            file_path = new_path  # ✅ Update file path after renaming

            file_size = os.path.getsize(file_path)
            file_size_mb = round(file_size / (1024 * 1024), 2)  # Display file size in MB
            logger.info(f"✅ File Size: {file_size_mb} MB")

            # ✅ Await async function & check for None
            thumbnail_path = await generate_thumbnail(file_path)

            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"✅ Thumbnail generated: {thumbnail_path}")
            else:
                logger.warning("⚠️ Thumbnail generation failed.")

            logger.info(f"✅ Download completed: {file_path}")

            # Provide direct download link for large files (ensure it's within a request context)
            if file_size > TELEGRAM_FILE_LIMIT:
                logger.info("⚠️ File too large for Telegram. Generating direct download link...")

                # ✅ Use `app.app_context()` to create a valid Flask context
                with app.app_context():
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