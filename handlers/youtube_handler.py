from download.yt_dlp_download import download_video
import telebot

def register(bot: telebot.TeleBot):
    @bot.message_handler(func=lambda message: is_supported_domain(message.text) and 'youtube' in get_domain(message.text))
    def handle_youtube(message):
        url = message.text.strip()
        bot.reply_to(message, "Processing your YouTube video download...")
        file_path, file_size = download_video(url)
        if file_path:
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video)
            os.remove(file_path)
        else:
            bot.reply_to(message, "Error downloading the video.")
