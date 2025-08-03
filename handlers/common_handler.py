import os
import asyncio
import logging
import yt_dlp
from pathlib import Path
from contextlib import asynccontextmanager
from utils.logger import setup_logging
from utils.sanitize import sanitize_filename
from utils.renamer import rename_file
from utils.thumb_generator import generate_thumbnail
from config import DOWNLOAD_DIR, TELEGRAM_FILE_LIMIT

# Setup logger
logger = setup_logging(logging.DEBUG)

@asynccontextmanager
async def yt_dlp_context(ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        yield ydl

async def compress_video(input_file, output_file):
    cmd = [
        "ffmpeg", "-i", input_file,
        "-c:v", "libx264", "-crf", "23", "-preset", "medium",
        "-c:a", "aac", "-b:a", "128k",
        output_file
    ]
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
        if process.returncode == 0:
            logger.info(f"✅ Video compressed: {output_file}")
            return output_file
        else:
            logger.error(f"❌ Compression failed:\n{stderr.decode().strip()}")
    except asyncio.TimeoutError:
        logger.error("❌ Compression timeout. Killing process...")
        process.kill()
    return None

async def process_adult(url: str):
    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
    file_path = None

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{sanitize_filename("%(title).100s")}.%(ext)s',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 15,
        'continuedl': True,
        'ignoreerrors': True,
        'nooverwrites': False,
        'quiet': True,
        'no_warnings': True,
        'concurrent_fragment_downloads': 4,
        'logger': logger,
        'http_chunk_size': 1048576,  # 1 MB
        'nocheckcertificate': True,
        'source_address': '0.0.0.0',
        'headers': {
            'User-Agent': 'Mozilla/5.0',
            'Referer': url
        }
    }

    try:
        async with yt_dlp_context(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            if not info:
                logger.error("❌ No info_dict returned from yt-dlp.")
                return None, 0, None

            file_path = Path(ydl.prepare_filename(info))
            if not file_path.exists():
                alt_path = file_path.with_suffix('.mp4')
                if alt_path.exists():
                    file_path = alt_path
                else:
                    logger.error("❌ Downloaded file not found.")
                    return None, 0, None

            sanitized_filename = sanitize_filename(file_path.name)
            new_path = file_path.parent / sanitized_filename
            if file_path != new_path:
                await rename_file(str(file_path), str(new_path))
                file_path = new_path

            file_size = file_path.stat().st_size
            logger.info(f"✅ File size: {file_size / (1024 ** 2):.2f} MB")

            thumbnail_path = await generate_thumbnail(str(file_path))
            if thumbnail_path:
                logger.info(f"✅ Thumbnail created: {thumbnail_path}")
            else:
                logger.warning("⚠️ Thumbnail creation failed.")

            if file_size > TELEGRAM_FILE_LIMIT:
                logger.info("⚠️ File too large, attempting compression...")
                compressed_file_path = file_path.with_stem(f"{file_path.stem}_compressed")
                compressed = await compress_video(str(file_path), str(compressed_file_path))

                if compressed and Path(compressed).stat().st_size < TELEGRAM_FILE_LIMIT:
                    logger.info("✅ Compression successful.")
                    return str(compressed), Path(compressed).stat().st_size, thumbnail_path

                logger.warning("⚠️ Compression failed or still too large.")
                return str(file_path), file_size, thumbnail_path

            return str(file_path), file_size, thumbnail_path

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ yt-dlp download error: {e}")
    except KeyError as e:
        if 'videoModel' in str(e):
            logger.error("❌ XHamster extractor broken. Wait for yt-dlp update.")
        else:
            logger.error(f"❌ KeyError: {e}")
    except OSError as e:
        logger.error(f"❌ Filesystem error: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")

    if file_path and file_path.exists() and file_path.stat().st_size == 0:
        file_path.unlink()
        logger.info(f"🧹 Removed zero-size file: {file_path}")

    return None, 0, None