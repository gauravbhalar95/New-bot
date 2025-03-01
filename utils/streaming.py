import yt_dlp
import logging
import asyncio
from config import COOKIES_FILE

logger = logging.getLogger(__name__)

async def get_streaming_url(url):
    """
    Asynchronously fetches a streaming URL without downloading the video.
    """
    loop = asyncio.get_running_loop()

    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
        'cookiefile': COOKIES_FILE,  # Include cookies for login-protected videos
        'quiet': True,  # Prevent unnecessary logs
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://x.com/'
        }
    }

    def fetch():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                return info_dict.get('url')
        except Exception as e:
            logger.error(f"Error fetching streaming URL: {e}")
            return None

    return await loop.run_in_executor(None, fetch)