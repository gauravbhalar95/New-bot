import os
import asyncio
import yt_dlp
import logging
from apivideo import ApiVideoClient
from config import COOKIES_FILE, API_VIDEO_KEY
from utils.logger import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize api.video client
client = ApiVideoClient(API_VIDEO_KEY)
videos_api = client.videos()

async def get_streaming_url(url):
    """Fetches a direct MP4 streaming URL and uploads to api.video."""
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
                download_url = info_dict.get('webpage_url')

                if video_url:
                    print(f"✅ Streaming URL: {video_url}")
                else:
                    print("❌ Failed to extract MP4 URL.")

                return video_url, download_url
        except Exception as e:
            logger.error(f"⚠️ Error fetching streaming URL: {e}")
            return None, None

    video_url, download_url = await loop.run_in_executor(None, fetch)

    if video_url:
        try:
            # Upload to api.video
            video_response = videos_api.upload(video_url)
            api_video_link = video_response["assets"]["hls"]  # Get HLS link

            return api_video_link, download_url
        except Exception as e:
            logger.error(f"⚠️ Error uploading to api.video: {e}")
            return None, None
    return None, None

async def send_streaming_options(bot, chat_id, streaming_url, download_url):
    """Sends the streaming link from api.video and original download link."""
    if not streaming_url:
        await bot.send_message(chat_id, "⚠️ **Failed to fetch streaming link. Try again!**")
        return

    message = (
        "🎬 **Streaming & Download Links:**\n\n"
        f"▶ **[Watch Online]({streaming_url})**\n"
        f"⬇️ **[Download Video]({download_url})**"
    )

    await bot.send_message(chat_id, message, parse_mode="Markdown")