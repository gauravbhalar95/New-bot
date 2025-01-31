# For example, handling "xvideos.com"
from download.xvideos_download import download_xvideo
import telebot

def register(bot: telebot.TeleBot):
    @bot.message_handler(func=lambda message: is_supported_domain(message.text) and 'xvideos' in get_domain(message.text))
    def handle_xvideos(message):
        url = message.text.strip()
        bot.reply_to(message, "Processing your Xvideos video download...")
        file_path = download_xvideos(url)
        if file_path:
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video)
            os.remove(file_path)
        else:
            bot.reply_to(message, "Error downloading from Xvideos.")
