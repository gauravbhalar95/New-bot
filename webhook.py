import os
import asyncio  # Added for async support
import urllib3
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import telebot
from telebot.async_telebot import AsyncTeleBot
from config import API_TOKEN, WEBHOOK_URL, PORT
from utils.logger import *

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")

# Flask app for webhook
app = Flask(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
async def webhook():
    """Handles incoming Telegram updates."""
    try:
        data = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(data)
        await bot.process_new_updates([update])
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
async def set_webhook():
    """Sets the Telegram webhook."""
    try:
        await bot.remove_webhook()
        success = await bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}", timeout=60)
        if success:
            return "Webhook set successfully", 200
        else:
            return "Failed to set webhook", 500
    except Exception as e:
        logger.error(f"Webhook setup failed: {e}")
        return f"Error: {str(e)}", 500

async def start_app():
    """Handles async setup before starting the Flask app."""
    await bot.remove_webhook()
    await bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}")
    logger.info(f"Starting Flask webhook server on port {PORT}...")
    app.run(host='0.0.0.0', port=PORT, debug=True)

if __name__ == '__main__':
    asyncio.run(start_app())