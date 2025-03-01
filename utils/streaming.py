import yt_dlp
import logging
import asyncio
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import COOKIES_FILE

logger = logging.getLogger(__name__)

async def get_streaming_url(url):
    """
    Asynchronously fetches a streaming URL (MP4 format only) with a Download Option.
    """
    loop = asyncio.get_running_loop()

    ydl_opts = {
        'format': 'best[ext=mp4]/best',  # ✅ Ensure MP4 Streaming URL
        'noplaylist': True,
        'cookiefile': COOKIES_FILE,  # ✅ Include cookies for login-protected videos
        'quiet': True,  # ✅ Prevent unnecessary logs
        'nocheckcertificate': True,  # ✅ Ignore SSL Errors
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': url  # ✅ Set Referer for Restricted Websites
        }
    }

    def fetch():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                return info_dict.get('url')
        except Exception as e:
            logger.error(f"⚠️ Error fetching streaming URL: {e}")
            return None

    return await loop.run_in_executor(None, fetch)

async def send_streaming_options(bot, chat_id, video_url):
    """
    Sends Streaming URL with a 'Download' button.
    """
    if not video_url:
        await bot.send_message(chat_id, "⚠️ **Failed to fetch streaming link. Try again!**")
        return

    # 🎥 Streaming URL Message
    stream_message = f"🎬 **Streaming Link:**\n[▶ Watch Video]({video_url})"

    # 📥 Download Button
    keyboard = InlineKeyboardMarkup()
    download_button = InlineKeyboardButton("📥 Download", url=video_url)
    keyboard.add(download_button)

    await bot.send_message(chat_id, stream_message, reply_markup=keyboard, parse_mode="Markdown")