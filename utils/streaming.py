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
    """Fetches the highest quality streaming & download link in the same format."""
    loop = asyncio.get_running_loop()

    ydl_opts = {
        'format': 'bv*+ba/best',  # Best video + audio
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
                best_video_url = info_dict.get('url')
                best_format = info_dict.get('ext')

                if best_video_url and best_format:
                    logger.info(f"✅ Selected Format: {best_format.upper()}")
                    
                    # Convert M3U8/DASH to MP4 with no quality loss
                    if best_format in ["m3u8", "mpd"]:
                        converted_link = convert_to_mp4(best_video_url)
                        return converted_link, "mp4"

                    return best_video_url, best_format
                else:
                    logger.error("❌ Failed to extract best format URL.")
                    return None, None
        except Exception as e:
            logger.error(f"⚠️ Error fetching video: {e}")
            return None, None

    return await loop.run_in_executor(None, fetch)

def convert_to_mp4(video_url):
    """Converts M3U8/DASH stream to MP4 without quality loss and provides a download link."""
    output_file = "converted_video.mp4"

    command = [
        "ffmpeg", "-i", video_url, "-c:v", "copy", "-c:a", "copy",
        "-bsf:a", "aac_adtstoasc", "-movflags", "+faststart",
        output_file, "-y"
    ]

    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if process.returncode == 0 and os.path.exists(output_file):
        logger.info(f"✅ Lossless MP4 Conversion: {output_file}")
        
        # Upload MP4 to a server or MEGA and return the link
        from handlers.mega_handlers import MegaNZ
        mega = MegaNZ()
        upload_link = mega.upload_file(output_file)

        return upload_link if upload_link else output_file
    else:
        logger.error("❌ Failed to convert video.")
        return None

async def download_best_clip(video_url, duration):
    """Downloads a 1-minute best scene clip from the video."""
    clip_path = "best_scene.mp4"
    
    try:
        duration = int(duration)  # Ensure duration is an integer
    except ValueError:
        return None  # If conversion fails, return None

    start_time = max(0, duration // 3)  # Now division will work correctly

    command = [
        "ffmpeg", "-i", video_url, "-ss", str(start_time),
        "-t", "60", "-c:v", "libx264", "-c:a", "aac",
        "-b:a", "128k", "-preset", "fast", clip_path, "-y"
    ]

    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return clip_path if process.returncode == 0 and os.path.exists(clip_path) else None
async def send_streaming_options(bot, chat_id, video_url, format_ext, clip_path):
    """Sends streaming and download links in the same format."""
    if not video_url:
        await bot.send_message(chat_id, "⚠️ **Failed to fetch streaming link. Try again!**")
        return

    message = f"🎬 **Streaming & Download Link ({format_ext.upper()}):**\n[▶ Watch / Download]({video_url})"

    await bot.send_message(chat_id, message, parse_mode="Markdown")

    if clip_path:
        with open(clip_path, "rb") as clip:
            await bot.send_video(chat_id, clip, caption="🎞 **Best 1-Min Scene Clip!**")
        os.remove(clip_path)