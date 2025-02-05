import os
import telebot
import yt_dlp
import cloudscraper
import imageio_ffmpeg
from moviepy import VideoFileClip
from config import API_TOKEN  # ✅ Import API Token

# ✅ Set up FFmpeg path
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
os.environ["IMAGEIO_FFMPEG_EXE"] = FFMPEG_PATH

# ✅ Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

# ✅ CloudScraper settings
scraper = cloudscraper.create_scraper()

# ✅ Supported adult sites
SUPPORTED_SITES = [
    "xvideos.com", "xnxx.com", "xhamster.com", "pornhub.com",
    "redtube.com", "tube8.com", "spankbang.com"
]

# ✅ Generate a thumbnail from the video
def generate_thumbnail(video_path):
    """Generate a thumbnail from the middle of the video."""
    try:
        if not os.path.exists(video_path):
            return None

        clip = VideoFileClip(video_path)
        thumbnail_path = video_path.replace(".mp4", ".jpg")
        clip.save_frame(thumbnail_path, t=clip.duration / 2)  # Take a frame from the middle
        clip.close()
        return thumbnail_path
    except Exception:
        return None

# ✅ Download video using yt-dlp
def process_adult(url):
    """Download video and return file path, size, and thumbnail."""
    try:
        output_template = "downloaded_video.%(ext)s"
        ydl_opts = {'outtmpl': output_template, 'format': 'best'}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        if not os.path.exists(file_path):
            return None, None, None

        file_size = os.path.getsize(file_path)
        thumb_path = generate_thumbnail(file_path)
        return file_path, file_size, thumb_path
    except Exception:
        return None, None, None

# ✅ Handle /start command
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(message.chat.id, "🔹 Send me a **video link** from supported sites.")

# ✅ Handle video download request
@bot.message_handler(func=lambda msg: True)
def handle_message(message):
    url = message.text.strip()

    if not any(site in url for site in SUPPORTED_SITES):
        bot.reply_to(message, "❌ Invalid URL. Please send a valid **video link**.")
        return

    bot.reply_to(message, "🔄 Downloading... Please wait.")

    file_path, file_size, thumb_path = download_video(url)

    if file_path:
        with open(file_path, 'rb') as video_file:
            try:
                if thumb_path:
                    with open(thumb_path, 'rb') as thumb:
                        bot.send_video(
                            message.chat.id, video_file,
                            caption=f"✅ Downloaded: {os.path.basename(file_path)} ({file_size / (1024 * 1024):.2f} MB)",
                            thumb=thumb
                        )
                    os.remove(thumb_path)  # ✅ Delete thumbnail
                else:
                    bot.send_video(
                        message.chat.id, video_file,
                        caption=f"✅ Downloaded: {os.path.basename(file_path)} ({file_size / (1024 * 1024):.2f} MB)"
                    )
            except Exception:
                bot.reply_to(message, "⚠️ Error sending video.")

        os.remove(file_path)  # ✅ Delete after sending
    else:
        bot.reply_to(message, "❌ Failed to download video. Please try another link.")

# ✅ Run the bot
