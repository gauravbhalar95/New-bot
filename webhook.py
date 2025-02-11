import logging
from flask import Flask, request
import telebot
from config import API_TOKEN, WEBHOOK_URL, PORT

# ✅ Initialize bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# ✅ Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ✅ Flask app
app = Flask(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
def webhook():
    """Handles Telegram webhook updates."""
    try:
        bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
        return "OK", 200
    except Exception as e:
        logger.error(f"⚠️ Webhook error: {e}")
        return "ERROR", 500

@app.route('/set_webhook')
def set_webhook():
    """Sets the webhook for Telegram."""
    try:
        bot.remove_webhook()
        bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}", timeout=60)
        return "✅ Webhook set successfully", 200
    except Exception as e:
        logger.error(f"⚠️ Webhook setup error: {e}")
        return "ERROR", 500

@app.route('/health')
def health_check():
    """Health check endpoint to prevent Koyeb from stopping the service."""
    return "✅ Health Check OK", 200

if __name__ == '__main__':
    # Run the Flask app
    app.run(host='0.0.0.0', port=int(PORT), debug=True)