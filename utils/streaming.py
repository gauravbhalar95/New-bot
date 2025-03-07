import yt_dlp
import logging
import asyncio
import os
import subprocess
from config import COOKIES_FILE

logger = logging.getLogger(__name__)

async def get_streaming_url(url):
    """Fetches a direct MP4 streaming & download URL."""
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
                if not info_dict:
                    return None, None, None

                video_url = info_dict.get('url')
                duration = info_dict.get('duration', 0)
                return video_url, duration, video_url  # Download URL is the same
        except Exception as e:
            logger.error(f"⚠️ Error fetching streaming/download URL: {e}")
            return None, None, None

    return await loop.run_in_executor(None, fetch)

async def download_best_clip(video_url, duration):
    """Downloads a 1-minute best scene clip from the video."""
    clip_path = "best_scene.mp4"
    start_time = max(0, duration // 3)  # Start at 1/3rd of the video

    command = [
        "ffmpeg", "-i", video_url, "-ss", str(start_time),
        "-t", "60", "-c:v", "libx264", "-c:a", "aac",
        "-b:a", "128k", "-preset", "fast", "-y", clip_path
    ]

    process = await asyncio.create_subprocess_exec(*command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await process.communicate()

    return clip_path if process.returncode == 0 and os.path.exists(clip_path) else None

async def send_streaming_options(bot, chat_id, video_url, clip_path, download_url):
    """Sends streaming URL, high-quality download link, and a 1-minute clip."""
    if not video_url:
        await bot.send_message(chat_id, "⚠️ **Failed to fetch streaming link. Try again!**")
        return

    message = (
        f"🎬 **Streaming Link:**\n[▶ Watch Video]({video_url})\n\n"
        f"📥 **Download in High Quality:**\n[🔗 Download Video]({download_url})"
    )
    await bot.send_message(chat_id, message, parse_mode="Markdown")

    if clip_path:
        async with aiofiles.open(clip_path, "rb") as clip:
            await bot.send_video(chat_id, clip, caption="🎞 **Best 1-Min Scene Clip!**")
        os.remove(clip_path)  # Cleanup file