import os
import logging
import asyncio
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Update
from config import API_TOKEN, WEBHOOK_URL, PORT

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")

# Create Flask app
app = Flask(__name__)

@app.route(f"/{API_TOKEN}", methods=["POST"])
async def telegram_webhook():
    """Handle webhook POST requests from Telegram."""
    try:
        json_str = await request.get_data()
        update = Update.de_json(json_str.decode("utf-8"))
        await bot.process_new_updates([update])
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.exception("Webhook processing failed")
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def home():
    return "Telegram bot is up!", 200

async def setup_webhook():
    """Set webhook safely in an async context."""
    await bot.remove_webhook()
    success = await bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}", timeout=60)
    if success:
        logger.info("Webhook set successfully.")
    else:
        logger.error("Failed to set webhook.")

def run():
    """Run the bot with Flask and setup webhook."""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup_webhook())
    app.run(host="0.0.0.0", port=int(PORT), debug=False)

if __name__ == "__main__":
    run()