import yt_dlp
import logging
import asyncio
from config import COOKIES_FILE
from utils.logger import setup_logging

logger = logging.getLogger(__name__)

async def get_streaming_url(url):
    """Fetches a direct MP4 streaming URL and provides a downloadable link."""
    loop = asyncio.get_running_loop()

    ydl_opts = {
        'format': 'bv*+ba/best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'cookiefile': COOKIES_FILE,
        'quiet': True,
        'nocheckcertificate': True
    }

    def fetch():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                video_url = info_dict.get('url')
                webpage_url = info_dict.get('webpage_url')  # Original page link for downloading

                if video_url:
                    logger.info(f"✅ Streaming URL: {video_url}")
                else:
                    logger.error("❌ Failed to extract MP4 URL.")

                return (video_url, webpage_url) if video_url else (None, None)  # ✅ Fixed return statement
        except Exception as e:
            logger.error(f"⚠️ Error fetching streaming URL: {e}")
            return None, None

    return await loop.run_in_executor(None, fetch)

async def send_streaming_options(bot, chat_id, video_url, download_url):
    """Sends streaming and download links."""
    if not video_url:
        await bot.send_message(chat_id, "⚠️ **Failed to fetch streaming link. Try again!**")
        return

    message = f"🎬 **Streaming & Download Links:**\n\n"
    message += f"▶ **[Watch Online]({video_url})**\n"
    message += f"⬇️ **[Download Video]({download_url})**"

    await bot.send_message(chat_id, message, parse_mode="Markdown")