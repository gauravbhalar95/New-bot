import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import telebot
from telebot.async_telebot import AsyncTeleBot
from urllib.parse import urljoin
import asyncio
import time
from config import API_TOKEN, WEBHOOK_URL, PORT

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")

# Define webhook path
WEBHOOK_PATH = urljoin(WEBHOOK_URL.rstrip('/'), f"/{API_TOKEN}")

# Flask app for webhook
app = Flask(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
async def webhook():
    """Handles incoming Telegram updates asynchronously."""
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
    """Ensures webhook is correctly set and handles conflicts automatically."""
    try:
        logger.info("Checking existing webhook status...")
        webhook_info = await bot.get_webhook_info()

        # If a conflicting webhook is found, remove it
        if webhook_info.url and webhook_info.url != WEBHOOK_PATH:
            logger.warning(f"Conflict detected: Existing webhook URL -> {webhook_info.url}")
            await bot.remove_webhook()
            time.sleep(2)  # Delay to ensure Telegram clears the old webhook
            logger.info("Previous webhook removed successfully.")

        # Set the new webhook
        success = await bot.set_webhook(url=WEBHOOK_PATH, timeout=120)
        if success:
            logger.info("Webhook successfully set.")
            return "Webhook set successfully", 200
        else:
            logger.error("Failed to set webhook.")
            return "Failed to set webhook", 500
    except Exception as e:
        logger.error(f"Webhook setup failed: {e}")
        return f"Error: {str(e)}", 500

@app.before_request
async def startup():
    """Ensure webhook is set before starting the Flask server."""
    await set_webhook()

if __name__ == '__main__':
    try:
        logger.info(f"Starting Flask webhook server on port {PORT}...")
        app.run(host='0.0.0.0', port=PORT)
        logger.info(f"Flask webhook server stopped.")
    except Exception as e:
        logger.error(f"Server failed to start: {e}")