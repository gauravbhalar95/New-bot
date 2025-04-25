import os
import logging
import asyncio
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import telebot
from telebot.async_telebot import AsyncTeleBot
from config import API_TOKEN, WEBHOOK_URL, PORT

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")

# Flask app for webhook
app = Flask(__name__)

@app.route(f"/{API_TOKEN}", methods=["POST"])
def webhook():
    """Handles incoming Telegram updates."""
    try:
        update = request.get_json()  # No need for 'await'
        if update:
            asyncio.create_task(bot.process_new_updates([telebot.types.Update.de_json(update)]))  # Run async task
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    """Root endpoint"""
    return "Telegram bot is running!", 200

def set_webhook():
    """Sets the Telegram webhook manually."""
    asyncio.run(bot.remove_webhook())
    success = asyncio.run(bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}", timeout=60))
    if success:
        logger.info("Webhook set successfully")
    else:
        logger.error("Failed to set webhook")

if __name__ == "__main__":
    set_webhook()  # Set webhook manually
    logger.info(f"Starting Flask webhook server on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT, debug=True)