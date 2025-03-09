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
    """Fetches the best quality streaming & download links."""
    loop = asyncio.get_running_loop()

    ydl_opts = {
        'format': 'bv*+ba/bestvideo[ext=mp4]+bestaudio/best',
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

                # Extract streaming URL
                video_url = info_dict.get('url')

                # Extract all available formats
                formats = info_dict.get('formats', [])
                best_download_url = None
                best_resolution = 0
                m3u8_url = None  # Store M3U8 URL

                download_links = []

                for fmt in formats:
                    format_url = fmt.get('url')
                    format_ext = fmt.get('ext', 'unknown')
                    format_res = fmt.get('height', 0)  # Extract resolution in pixels

                    if format_url:
                        # Store all available formats
                        download_links.append({
                            "format": format_ext,
                            "resolution": f"{format_res}p" if format_res else "unknown",
                            "url": format_url
                        })

                        # Choose the highest quality format (MP4/MKV preferred)
                        if format_res > best_resolution and format_ext in ['mp4', 'mkv']:
                            best_resolution = format_res
                            best_download_url = format_url

                        # Store M3U8 URL if available
                        if format_ext == 'm3u8':
                            m3u8_url = format_url

                # If no MP4/MKV, fall back to the highest available quality
                if not best_download_url and download_links:
                    best_download_url = download_links[-1]['url']

                # Convert M3U8 to MP4 if available
                if m3u8_url:
                    logger.info(f"🎥 M3U8 stream found: {m3u8_url}")
                    converted_mp4 = convert_m3u8_to_mp4(m3u8_url)
                    if converted_mp4:
                        best_download_url = converted_mp4

                logger.info(f"✅ Streaming URL: {video_url}")
                logger.info(f"⬇️ Best Download URL ({best_resolution}p): {best_download_url}")
                logger.info(f"📂 Available Download Links: {download_links}")

                return video_url, best_download_url, download_links
        except Exception as e:
            logger.error(f"⚠️ Error fetching streaming URL: {e}")
            return None, None, []

    return await loop.run_in_executor(None, fetch)

def convert_m3u8_to_mp4(m3u8_url):
    """Converts an M3U8 stream to MP4 using FFmpeg."""
    output_file = "converted_video.mp4"

    command = [
        "ffmpeg", "-i", m3u8_url, "-c:v", "libx264", "-c:a", "aac", "-strict", "experimental",
        "-b:a", "128k", "-preset", "fast", "-f", "mp4", output_file, "-y"
    ]

    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if process.returncode == 0 and os.path.exists(output_file):
        logger.info(f"✅ M3U8 successfully converted to MP4: {output_file}")
        return output_file
    else:
        logger.error("❌ M3U8 to MP4 conversion failed.")
        return None

async def send_streaming_options(bot, chat_id, video_url, best_download_url, download_links):
    """Sends streaming URL, best quality download link, and all available formats."""
    if not video_url:
        await bot.send_message(chat_id, "⚠️ **Failed to fetch streaming link. Try again!**")
        return

    # Build the message
    message = f"🎬 **Streaming Link:**\n▶ [Watch Online]({video_url})\n\n"

    # Best download link (highest quality)
    if best_download_url:
        message += f"⬇️ **Best Quality Download:** [Download Here]({best_download_url})\n\n"

    # All available formats
    if download_links:
        message += "📂 **Other Available Formats:**\n"
        for link in download_links:
            message += f"📁 `{link['format']}` ({link['resolution']}): [Download]({link['url']})\n"

    await bot.send_message(chat_id, message, parse_mode="Markdown")