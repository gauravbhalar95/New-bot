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
        update = request.get_json()

        if update:
            telegram_update = telebot.types.Update.de_json(update)

            # Flask thread has no running event loop
            asyncio.run(
                bot.process_new_updates([telegram_update])
            )

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    """Root endpoint"""
    return "Telegram bot is running!", 200

async def set_webhook():
    """Set Telegram webhook only if it is not already set."""
    try:
        info = await bot.get_webhook_info()

        if info.url == f"{WEBHOOK_URL}/{API_TOKEN}":
            logger.info("Webhook already set. Skipping...")
            return

        success = await bot.set_webhook(
            url=f"{WEBHOOK_URL}/{API_TOKEN}",
            timeout=60
        )

        if success:
            logger.info("Webhook set successfully")
        else:
            logger.error("Failed to set webhook")

    except Exception as e:
        logger.error(f"Webhook error: {e}")


if __name__ == "__main__":
    asyncio.run(set_webhook())

    logger.info(f"Starting Flask webhook server on port {PORT}...")

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False
    )