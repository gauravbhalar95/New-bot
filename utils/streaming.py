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

async def get_streaming_url(url):
    """Fetches a direct MP4 streaming URL and gets video duration."""
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

                # Extract the main streaming URL
                video_url = info_dict.get('url')

                # Extract all available formats
                formats = info_dict.get('formats', [])
                download_links = []

                for fmt in formats:
                    format_url = fmt.get('url')
                    format_ext = fmt.get('ext', 'unknown')
                    format_res = fmt.get('format_note', 'unknown')

                    if format_url:
                        download_links.append({
                            "format": format_ext,
                            "resolution": format_res,
                            "url": format_url
                        })

                logger.info(f"✅ Streaming URL: {video_url}")
                logger.info(f"⬇️ Available Download Links: {download_links}")

                return video_url, download_links
        except Exception as e:
            logger.error(f"⚠️ Error fetching streaming URL: {e}")
            return None, []

    return await loop.run_in_executor(None, fetch)

async def download_best_clip(video_url, duration):
    """Downloads a 1-minute best scene clip from the video."""
    clip_path = "best_scene.mp4"
    start_time = max(0, duration // 3)

    command = [
        "ffmpeg", "-i", video_url, "-ss", str(start_time),
        "-t", "60", "-c:v", "libx264", "-c:a", "aac",
        "-b:a", "128k", "-preset", "fast", clip_path, "-y"
    ]

    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return clip_path if process.returncode == 0 and os.path.exists(clip_path) else None

async def send_streaming_options(bot, chat_id, video_url, download_links):
    """Sends streaming URL and all available download links."""
    if not video_url:
        await bot.send_message(chat_id, "⚠️ **Failed to fetch streaming link. Try again!**")
        return

    # Start message with streaming link
    message = f"🎬 **Streaming Link:**\n▶ [Watch Online]({video_url})\n\n"

    # Add all download links
    if download_links:
        message += "⬇️ **Download Links:**\n"
        for link in download_links:
            message += f"📁 `{link['format']}` ({link['resolution']}): [Download]({link['url']})\n"

    await bot.send_message(chat_id, message, parse_mode="Markdown")