import yt_dlp
import logging
import asyncio
import os
import subprocess
import apivideo
from apivideo.apis import VideosApi
from config import COOKIES_FILE, API_VIDEO_KEY
from utils.logger import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

class ApiVideoClient:
    def __init__(self, api_key=API_VIDEO_KEY):
        self.api_key = api_key
        self.client = apivideo.AuthenticatedApiClient(self.api_key)
        self.videos_api = VideosApi(self.client)

    def list_videos(self):
        """Fetch all videos from api.video."""
        try:
            response = self.videos_api.list()
            return response.get("data", [])
        except Exception as e:
            logger.error(f"⚠️ Error fetching videos: {e}")
            return []

    def get_video_links(self):
        """Get streaming and download links for all videos."""
        videos = self.list_videos()
        video_links = []

        for video in videos:
            video_id = video['videoId']
            title = video.get('title', 'No Title')
            streaming_link = f"https://embed.api.video/vod/{video_id}"
            download_link = video.get('assets', {}).get('mp4')

            video_links.append({
                "title": title,
                "streaming_link": streaming_link,
                "download_link": download_link
            })

        return video_links

async def download_best_clip(url):
    """Fetches the best quality streaming & download link in the same format."""
    loop = asyncio.get_running_loop()

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best',
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

                # Extract best format URL
                best_video_url = info_dict.get('url')
                best_format = info_dict.get('ext')

                if best_video_url and best_format:
                    logger.info(f"✅ Selected Format: {best_format.upper()}")
                    logger.info(f"🎬 Streaming & Download Link: {best_video_url}")
                    return best_video_url, best_format
                else:
                    logger.error("❌ Failed to extract best format URL.")
                    return None, None
        except Exception as e:
            logger.error(f"⚠️ Error fetching video: {e}")
            return None, None

    return await loop.run_in_executor(None, fetch)

async def send_streaming_options(bot, chat_id, video_url, format_ext):
    """Sends streaming and download links in the same format."""
    if not video_url:
        await bot.send_message(chat_id, "⚠️ **Failed to fetch streaming link. Try again!**")
        return

    message = f"🎬 **Streaming & Download Link ({format_ext.upper()}):**\n[▶ Watch / Download]({video_url})"

    await bot.send_message(chat_id, message, parse_mode="Markdown")