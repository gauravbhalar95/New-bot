import os
import telebot
import yt_dlp
import cloudscraper
import imageio_ffmpeg
from moviepy import VideoFileClip
from config import API_TOKEN  # ✅ Import API Token from config

# ✅ Set FFmpeg path manually if needed
os.environ["IMAGEIO_FFMPEG_EXE"] = imageio_ffmpeg.get_ffmpeg_exe()

bot = telebot.TeleBot(API_TOKEN)

# ✅ Headers for requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Connection": "keep-alive"
}

scraper = cloudscraper.create_scraper()

# ✅ Function to generate a thumbnail from the video
def generate_thumbnail(video_path):
    try:
        clip = VideoFileClip(video_path)
        thumbnail_path = video_path.replace(".mp4", ".jpg")
        clip.save_frame(thumbnail_path, t=clip.duration / 2)  # Take a frame from the middle
        clip.close()
        return thumbnail_path
    except Exception as e:
        print(f"❌ Thumbnail Error: {e}")
        return None

# ✅ Function to process adult video downloads using yt-dlp
def process_adult(url):
    try:
        output_template = "downloaded_video.%(ext)s"
        ydl_opts = {
            'outtmpl': output_template,
            'format': 'best',
            'quiet': True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)  # Get downloaded file name

        if not os.path.exists(file_path):
            return None, None, None

        file_size = os.path.getsize(file_path)
        thumb_path = generate_thumbnail(file_path)  # ✅ Generate thumbnail
        return file_path, file_size, thumb_path

    except Exception as e:
        print(f"❌ Download Error: {e}")
        return None, None, None

# ✅ Telegram Bot Handlers
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.reply_to(message, "🔹 Send me a video link from **XVideos, XNXX, XHamster, Pornhub, RedTube**, and I'll download it for you!")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()

    # ✅ Check if URL is valid
    if not any(site in url for site in ["xvideos.com", "xnxx.com", "xhamster.com", "pornhub.com", "redtube.com"]):
        bot.reply_to(message, "❌ Invalid URL. Please send a valid video link from **XVideos, XNXX, XHamster, Pornhub, or RedTube**.")
        return

    bot.reply_to(message, "🔄 Downloading... Please wait.")

    # ✅ Process the video
    file_path, file_size, thumb_path = process_adult(url)

    if file_path:
        with open(file_path, 'rb') as video_file:
            if thumb_path:
                with open(thumb_path, 'rb') as thumb:
                    bot.send_video(
                        message.chat.id,
                        video_file,
                        caption=f"✅ Downloaded: {os.path.basename(file_path)} ({file_size / (1024 * 1024):.2f} MB)",
                        thumb=thumb
                    )
                os.remove(thumb_path)  # Delete thumbnail
            else:
                bot.send_video(
                    message.chat.id,
                    video_file,
                    caption=f"✅ Downloaded: {os.path.basename(file_path)} ({file_size / (1024 * 1024):.2f} MB)"
                )
        os.remove(file_path)  # Delete after sending
    else:
        bot.reply_to(message, "❌ Failed to download video. Please try another link.")

# ✅ Start the bot
print("🚀 Bot is running...")
bot.polling(none_stop=True)