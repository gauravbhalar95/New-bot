import yt_dlp
import logging
import asyncio
import os
import subprocess
from config import COOKIES_FILE

logger = logging.getLogger(__name__)

async def get_download_url(url):
    """Fetches a direct MP4 download URL and gets video duration."""
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
                filesize = info_dict.get('filesize', 0)

                if video_url:
                    print(f"✅ Extracted Video URL: {video_url}")
                else:
                    print("❌ Failed to extract download URL.")

                return video_url, duration, filesize if video_url else (None, None, None)
        except Exception as e:
            logger.error(f"⚠️ Error fetching download URL: {e}")
            return None, None, None

    return await loop.run_in_executor(None, fetch)

async def download_best_clip(video_url, duration):
    """Downloads a 1-minute best scene clip from the video."""
    clip_path = "best_scene.mp4"
    start_time = max(0, duration // 3)  # Start at 1/3rd of the video

    command = [
        "ffmpeg", "-i", video_url, "-ss", str(start_time),
        "-t", "60", "-c:v", "libx264", "-c:a", "aac",
        "-b:a", "128k", "-preset", "fast", clip_path, "-y"
    ]

    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return clip_path if process.returncode == 0 and os.path.exists(clip_path) else None

async def send_download_options(bot, chat_id, video_url, clip_path, filesize):
    """Sends a download link and a 1-minute clip."""
    if not video_url:
        await bot.send_message(chat_id, "⚠️ **Failed to fetch download link. Try again!**")
        return

    if filesize and filesize > 2 * 1024 * 1024 * 1024:  # 2GB limit
        # Provide Download Link for Large Videos
        download_message = f"📥 **Download Link:**\n[⬇️ Download Video]({video_url})"
        await bot.send_message(chat_id, download_message, parse_mode="Markdown")
    else:
        # Upload directly if within Telegram limit
        await bot.send_video(chat_id, video_url, caption="📹 **Video Uploaded Directly!**")

    # 🎞 Send Best Scene Clip
    if clip_path:
        with open(clip_path, "rb") as clip:
            await bot.send_video(chat_id, clip, caption="🎞 **Best 1-Min Scene Clip!**")
        os.remove(clip_path)  # Cleanup file

async def handle_video_request(bot, chat_id, url):
    """Main handler to fetch and send video content."""
    video_url, duration, filesize = await get_download_url(url)

    if not video_url:
        await bot.send_message(chat_id, "❌ **Error: Unable to fetch video details.**")
        return

    clip_path = await download_best_clip(video_url, duration)
    await send_download_options(bot, chat_id, video_url, clip_path, filesize)