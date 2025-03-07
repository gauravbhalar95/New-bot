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

@app.route('/' + API_TOKEN, methods=['POST'])
async def webhook():
    """Handles incoming Telegram updates asynchronously."""
    try:
        data = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(data)
        await bot.process_new_updates([update])  # Await this async function
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return jsonify({"error": str(e)}), 500

async def set_webhook():
    """Asynchronously sets the Telegram webhook."""
    try:
        await bot.remove_webhook()  # Await async method
        success = await bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}", timeout=60)
        if success:
            logger.info("Webhook set successfully")
        else:
            logger.error("Failed to set webhook")
    except Exception as e:
        logger.error(f"Webhook setup failed: {e}")

if __name__ == '__main__':
    logger.info(f"Starting Flask webhook server on port {PORT}...")
    
    # Ensure webhook is set before starting Flask
    asyncio.run(set_webhook())  

    # Run Flask in a separate thread (since Flask is not async)
    app.run(host='0.0.0.0', port=PORT)