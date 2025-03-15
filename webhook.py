import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import telebot
from telebot.async_telebot import AsyncTeleBot
from urllib.parse import urljoin
from config import API_TOKEN, WEBHOOK_URL, PORT

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")

# Define webhook path
WEBHOOK_PATH = urljoin(WEBHOOK_URL, f"/{API_TOKEN}")

# Flask app for webhook
app = Flask(__name__)

webhook_set = False #Variable to track webhook status.

@app.route('/' + API_TOKEN, methods=['POST'])
async def webhook():
    """Handles incoming Telegram updates asynchronously."""
    try:
        data = await request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(data)
        await bot.process_new_updates([update])
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def set_webhook():
    """Sets the Telegram webhook."""
    global webhook_set
    try:
        if not webhook_set:
            bot.remove_webhook()
            success = bot.set_webhook(url=WEBHOOK_PATH, timeout=120)
            if success:
                webhook_set = True
                return "Webhook set successfully", 200
            else:
                return "Failed to set webhook", 500
        else:
            return "Webhook already set", 200

    except Exception as e:
        logger.error(f"Webhook setup failed: {e}")
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    try:
        logger.info(f"Starting Flask webhook server on port {PORT}...")
        app.run(host='0.0.0.0', port=PORT)
        logger.info(f"Flask webhook server stopped.") #Add stop logging.
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
