from PIL import Image
import os
import telebot
from download.xvideos_download import download_xvideo
from yt_dlp import YoutubeDL
from tempfile import NamedTemporaryFile

API_TOKEN = 'your_telegram_bot_api_token'

# Create the Telegram bot
bot = telebot.TeleBot(API_TOKEN)

def is_supported_domain(url):
    """
    Check if the URL is from a supported domain like xvideos.com.
    """
    return 'xvideos' in get_domain(url)

def get_domain(url):
    """
    Extract the domain name from the URL.
    """
    from urllib.parse import urlparse
    return urlparse(url).netloc

def download_xvideos(url):
    """
    Downloads the video from Xvideos and returns the file path.
    Uses yt-dlp to handle large videos and download them.
    """
    ydl_opts = {
        'format': 'best',  # Download the best available format
        'outtmpl': 'downloads/%(title)s.%(ext)s',  # Save to a specific directory
        'quiet': True,  # Suppress unnecessary output
        'noplaylist': True  # Don't download playlists
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            return file_path
    except Exception as e:
        print(f"Error downloading video: {e}")
        return None

def generate_thumbnail(video_path):
    """
    Generates a thumbnail for the video using Pillow.
    """
    # Open the first frame or use a thumbnail generator
    try:
        with Image.open(video_path) as img:
            img.thumbnail((128, 128))  # Resize to a smaller size
            thumb_path = f"{video_path}_thumbnail.jpg"
            img.save(thumb_path)
            return thumb_path
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return None

@bot.message_handler(func=lambda message: is_supported_domain(message.text) and 'xvideos' in get_domain(message.text))
def handle_xvideos(message):
    url = message.text.strip()
    bot.reply_to(message, "Processing your Xvideos video download...")

    # Download the video
    file_path = download_xvideos(url)
    if file_path:
        # Generate the thumbnail
        thumb_path = generate_thumbnail(file_path)

        # Send the thumbnail to the user
        if thumb_path:
            with open(thumb_path, 'rb') as thumb:
                bot.send_photo(message.chat.id, thumb)

        # Handle large video files by sending via stream
        try:
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video)
            os.remove(file_path)  # Clean up after sending
            if thumb_path:
                os.remove(thumb_path)  # Clean up the thumbnail as well
        except Exception as e:
            bot.reply_to(message, f"Error sending video: {e}")
            print(f"Error sending video: {e}")
    else:
        bot.reply_to(message, "Error downloading from Xvideos.")

# Start the bot
bot.polling()