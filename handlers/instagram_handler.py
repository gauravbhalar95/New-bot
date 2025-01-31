from download.instagram_download import download_instagram
import telebot

def register(bot: telebot.TeleBot):
    @bot.message_handler(func=lambda message: is_supported_domain(message.text) and 'instagram' in get_domain(message.text))
    def handle_instagram(message):
        url = message.text.strip()
        bot.reply_to(message, "Processing your Instagram video download...")
        file_path = download_instagram(url)
        if file_path:
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video)
            os.remove(file_path)
        else:
            bot.reply_to(message, "Error downloading from Instagram.")
