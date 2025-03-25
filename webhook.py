import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import telebot
from telebot.async_telebot import AsyncTeleBot
from config import API_TOKEN, WEBHOOK_URL, PORT


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")

# Flask app for webhook
app = Flask(__name__)

@app.route(f"/{API_TOKEN}", methods=["POST"])
async def webhook():
    """Handles incoming Telegram updates asynchronously."""
    try:
        update = await request.get_json()
        if update:
            await bot.process_new_updates([update])
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/")
async def set_webhook():
    """Sets the Telegram webhook asynchronously."""
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

async def start_server():
    """Starts the webhook server."""
    logger.info(f"Starting Flask webhook server on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    asyncio.run(start_server())  # Properly runs async Flask app