import logging
from flask import Flask, request
from bot import bot  # Import the bot instance
from config import API_TOKEN, WEBHOOK_URL, PORT

# ✅ Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ✅ Flask app for webhook
app = Flask(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
def webhook():
    """Webhook to process new updates."""
    try:
        bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
        return "OK", 200
    except Exception as e:
        logger.error(f"⚠️ Webhook error: {e}")
        return "ERROR", 500

@app.route('/')
def set_webhook():
    """Set the webhook for Telegram."""
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL + '/' + API_TOKEN, timeout=60)
        return "Webhook set", 200
    except Exception as e:
        logger.error(f"⚠️ Webhook setup error: {e}")
        return "ERROR", 500

if __name__ == '__main__':
    # Run the Flask app
    app.run(host='0.0.0.0', port=PORT)
