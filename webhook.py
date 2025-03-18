import os
import logging
import asyncio
from quart import Quart, request, jsonify
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

# Initialize Quart app
app = Quart(__name__)

@app.before_serving
async def startup():
    """Ensure webhook is properly set during startup."""
    await bot.remove_webhook()
    await bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}", timeout=60)
    logger.info("Webhook set successfully.")

@app.route('/' + API_TOKEN, methods=['POST'])
async def webhook():
    """Handle incoming Telegram updates."""
    try:
        data = await request.get_data()
        await bot.process_new_updates([telebot.types.Update.de_json(data.decode("utf-8"))])
        return "OK", 200
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return jsonify({"error": "Failed to process request"}), 500

@app.route('/')
async def index():
    """Health check endpoint."""
    return "Bot is running.", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)