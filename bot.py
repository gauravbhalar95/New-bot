import os
import logging
from flask import Flask, request
import telebot
from handlers.youtube_handler import process_youtube
from handlers.instagram_handler import process_instagram
from utils.thumb_generator import generate_thumbnail

# Load environment variables
API_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 8080))

# Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supported domains
SUPPORTED_DOMAINS = ["youtube.com", "youtu.be", "instagram.com", "x.com"]

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Send me a video link to download or stream.")

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    url = message.text.strip()
    
    if "youtube.com" in url or "youtu.be" in url:
        file_path, file_size, thumb_path = process_youtube(url)
    elif "instagram.com" in url:
        file_path, file_size, thumb_path = process_instagram(url)
    else:
        bot.reply_to(message, "Unsupported URL.")
        return
    
    if file_path:
        try:
            with open(file_path, 'rb') as video, open(thumb_path, 'rb') as thumb:
                bot.send_video(
                    message.chat.id, 
                    video, 
                    thumb=thumb, 
                    caption="Here is your downloaded video!"
                )
        except Exception as e:
            bot.reply_to(message, f"Error sending video: {e}")
    else:
        bot.reply_to(message, "Download failed.")

# Flask Webhook
app = Flask(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

@app.route('/')
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + '/' + API_TOKEN, timeout=60)
    return "Webhook set", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)