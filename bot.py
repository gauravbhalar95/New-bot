import os
import logging
import telebot
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from function.meganz import mega_login,upload_to_mega
from config import API_TOKEN

# ✅ Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# ✅ Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ✅ MEGA Login Session
mega = Mega()
mega_session = None

# ✅ Supported domains
SUPPORTED_DOMAINS = {
    "youtube": ["youtube.com", "youtu.be"],
    "instagram": ["instagram.com"],
    "twitter": ["x.com", "twitter.com"],
    "adult": ["xvideos.com", "xnxx.com", "xhamster.com", "pornhub.com", "redtube.com", 
              "tube8.com", "spankbang.com"],
    "mega": ["mega.nz"]
}

def detect_platform(url):
    """Detects the platform from the URL."""
    for platform, domains in SUPPORTED_DOMAINS.items():
        if any(domain in url for domain in domains):
            return platform
    return None

# ✅ MEGA Login Command
@bot.message_handler(commands=['meganz'])
def mega_login(message):
    global mega_session
    try:
        args = message.text.split()
        if len(args) != 3:
            bot.reply_to(message, "Usage: /meganz <email> <password>")
            return

        email, password = args[1], args[2]
        mega_session = mega.login(email, password)
        bot.reply_to(message, "✅ MEGA Login Successful!")
    except Exception as e:
        bot.reply_to(message, f"❌ MEGA Login Failed: {str(e)}")

# ✅ Upload to MEGA
def upload_to_mega(file_path, message):
    if mega_session is None:
        bot.reply_to(message, "❌ Please log in to MEGA first using /meganz <email> <password>")
        return
    
    try:
        uploaded_file = mega_session.upload(file_path)
        file_url = mega_session.get_upload_link(uploaded_file)
        bot.reply_to(message, f"✅ File Uploaded to MEGA: {file_url}")
    except Exception as e:
        bot.reply_to(message, f"❌ Upload Failed: {str(e)}")

# ✅ Download from MEGA
def download_from_mega(url, message):
    if mega_session is None:
        bot.reply_to(message, "❌ Please log in to MEGA first using /meganz <email> <password>")
        return
    
    try:
        mega_session.download_url(url, dest_path="./")
        bot.reply_to(message, "✅ MEGA File Downloaded Successfully!")
    except Exception as e:
        bot.reply_to(message, f"❌ MEGA Download Failed: {str(e)}")

# ✅ Handle incoming messages (URLs)
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    """Handles incoming messages and processes the URLs."""
    url = message.text.strip()
    platform = detect_platform(url)

    if not platform:
        bot.reply_to(message, "❌ Unsupported URL. Please send a valid link.")
        return

    bot.reply_to(message, f"⏳ Processing {platform.capitalize()}... Please wait.")

    try:
        if platform == "mega":
            download_from_mega(url, message)
        else:
            process_funcs = {
                "youtube": process_youtube,
                "instagram": process_instagram,
                "adult": lambda url: process_adult(url, message.chat.id),
                "twitter": lambda url: download_twitter_media(url, message.chat.id)
            }
            result = process_funcs.get(platform, lambda _: None)(url)

            if not result:
                bot.reply_to(message, "❌ Download failed. Please try again later.")
                return

            if isinstance(result, tuple) and len(result) in [2, 3]:
                file_path, file_size = result[:2]
                thumb_path = result[2] if len(result) == 3 else None
            else:
                bot.reply_to(message, "❌ Unexpected response from the downloader.")
                return

            if not os.path.exists(file_path):
                bot.reply_to(message, "❌ Error: File not found.")
                return

            with open(file_path, 'rb') as video:
                thumb = open(thumb_path, 'rb') if thumb_path and os.path.exists(thumb_path) else None
                bot.send_video(
                    message.chat.id,
                    video,
                    thumb=thumb,
                    caption=f"✅ Download complete! File size: {file_size / (1024 * 1024):.2f} MB"
                )
                if thumb:
                    thumb.close()

            logger.info(f"✔ Video sent: {file_path}")

            # ✅ Upload downloaded file to MEGA
            upload_to_mega(file_path, message)

    except Exception as e:
        logger.error(f"⚠️ Error processing request: {e}")
        bot.reply_to(message, f"❌ Error: {str(e)}")