import yt_dlp
import logging
import asyncio
from config import COOKIES_FILE

logger = logging.getLogger(__name__)

async def get_streaming_url(url):
    """Fetches a direct MP4 streaming URL."""
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
                return video_url if video_url else None
        except Exception as e:
            logger.error(f"⚠️ Error fetching streaming URL: {e}")
            return None

    return await loop.run_in_executor(None, fetch)

async def send_streaming_options(bot, chat_id, video_url):
    """Sends streaming and download links."""
    if not video_url:
        await bot.send_message(chat_id, "⚠️ **Failed to fetch streaming link. Try again!**")
        return

    # 🎥 Streaming URL
    stream_message = f"🎬 **Streaming Link:**\n[▶ Watch Video]({video_url})\n\n"
    stream_message += f"📥 **Download Link:**\n[⬇ Download Video]({video_url})"

    await bot.send_message(chat_id, stream_message, parse_mode="Markdown")