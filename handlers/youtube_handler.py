import os
import logging
from urllib.parse import urlparse
from download.yt_dlp_download import download_video
from config import SUPPORTED_DOMAINS
import telebot

logger = logging.getLogger(__name__)

def is_supported_domain(url):
    """
    Check if the URL belongs to a supported domain.
    """
    try:
        domain = urlparse(url).netloc
        return any(supported_domain in domain for supported_domain in SUPPORTED_DOMAINS)
    except Exception:
        return False

def get_domain(url):
    """
    Extract the domain from the URL.
    """
    return urlparse(url).netloc

def register(bot: telebot.TeleBot):
    @bot.message_handler(func=lambda message: is_supported_domain(message.text) and 'youtube' in get_domain(message.text))
    def handle_youtube(message):
        url = message.text.strip()
        logger.info(f"Processing YouTube URL: {url}")
        bot.reply_to(message, "Processing your YouTube video download...")
        file_path, file_size = download_video(url)
        if file_path:
            try:
                with open(file_path, 'rb') as video:
                    bot.send_video(message.chat.id, video)
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Error sending video: {e}")
                bot.reply_to(message, "Error sending the video.")
        else:
            bot.reply_to(message, "Error downloading the video.")