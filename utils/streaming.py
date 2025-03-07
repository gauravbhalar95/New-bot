import yt_dlp
import logging
import asyncio
import os
import subprocess
from config import COOKIES_FILE

logger = logging.getLogger(__name__)

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
                video_url = info_dict.get('url')
                duration = info_dict.get('duration', 0)

                if video_url:
                    logger.info(f"✅ Extracted Video URL: {video_url}")
                else:
                    logger.error("❌ Failed to extract MP4 URL.")

                return video_url, duration if video_url else (None, None)
        except Exception as e:
            logger.error(f"⚠️ Error fetching streaming URL: {e}")
            return None, None

    return await loop.run_in_executor(None, fetch)

async def download_best_clip(video_url, duration):
    """Downloads a 1-minute best scene clip from the video."""
    clip_path = "best_scene.mp4"
    
    if not duration:
        logger.error("⚠️ Video duration not found. Skipping clip download.")
        return None

    start_time = max(0, duration // 3)  # Start at 1/3rd of the video

    command = [
        "ffmpeg", "-i", video_url, "-ss", str(start_time),
        "-t", "60", "-c:v", "libx264", "-c:a", "aac",
        "-b:a", "128k", "-preset", "fast", "-y", clip_path
    ]

    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if process.returncode == 0 and os.path.exists(clip_path):
        logger.info("✅ Clip downloaded successfully.")
        return clip_path
    else:
        logger.error(f"❌ FFmpeg Error: {process.stderr}")
        return None

async def send_streaming_options(bot, chat_id, video_url, clip_path):
    """Sends streaming URL and a 1-minute clip."""
    if not video_url:
        await bot.send_message(chat_id, "⚠️ **Failed to fetch streaming link. Try again!**")
        return

    # 🎥 Streaming URL Message
    stream_message = f"🎬 **Streaming Link:**\n[▶ Watch Video]({video_url})"
    await bot.send_message(chat_id, stream_message, parse_mode="Markdown")

    # 🎞 Send Best Scene Clip
    if clip_path:
        try:
            with open(clip_path, "rb") as clip:
                await bot.send_video(chat_id, clip, caption="🎞 **Best 1-Min Scene Clip!**")
        except Exception as e:
            logger.error(f"❌ Error sending video: {e}")
        finally:
            os.remove(clip_path)  # Cleanup file