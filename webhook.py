import os
import logging
import asyncio
from quart import Quart, request  # Quart supports async
import telebot
from telebot.async_telebot import AsyncTeleBot
from hypercorn.asyncio import serve
from hypercorn.config import Config

# Load environment variables
API_TOKEN = os.getenv("API_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-app.koyeb.app

if not API_TOKEN or not WEBHOOK_URL:
    raise ValueError("❌ API_TOKEN or WEBHOOK_URL is missing. Please set them in environment variables.")

# Create async TeleBot instance
bot = AsyncTeleBot(API_TOKEN)
app = Quart(__name__)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Route to receive Telegram updates via webhook
@app.route(f"/{API_TOKEN}", methods=["POST"])
async def webhook():
    json_str = await request.data
    update = telebot.types.Update.de_json(json_str.decode("utf-8"))
    await bot.process_new_updates([update])
    return "", 200

# Route to confirm app is running
@app.route("/")
async def home():
    return "✅ Telegram bot webhook is running!"

# Define command handler
@bot.message_handler(commands=["start"])
async def start_handler(message):
    await bot.send_message(message.chat.id, "👋 Welcome! Your bot is working via webhook.")

# Function to set webhook URL
async def set_webhook():
    await bot.remove_webhook()
    await bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}")
    logger.info(f"🌍 Webhook set to: {WEBHOOK_URL}/{API_TOKEN}")

# Main entry point
if __name__ == "__main__":
    config = Config()
    config.bind = ["0.0.0.0:8080"]

    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_webhook())
    loop.run_until_complete(serve(app, config))