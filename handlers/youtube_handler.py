import os
import yt_dlp
import logging
from config import DOWNLOAD_DIR  

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_adult(url):
    """ adult વીડિયો ડાઉનલોડ કરવા માટે ફંક્શન """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'socket_timeout': 10,
        'retries': 5,
        'logger': logger,
        'verbose': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            
            if not info_dict:
                logger.error("⚠️ yt-dlp returned None. URL may be invalid.")
                return None, 0
            
            file_path = ydl.prepare_filename(info_dict)
            file_size = info_dict.get('filesize', 0)

            if not os.path.exists(file_path):
                logger.error(f"❌ Download failed. File not found: {file_path}")
                return None, 0

            logger.info(f"✅ Downloaded video: {file_path} (Size: {file_size} bytes)")
            return file_path, file_size

    except yt_dlp.DownloadError as e:
        logger.error(f"❌ Download Error: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")

    return None, 0