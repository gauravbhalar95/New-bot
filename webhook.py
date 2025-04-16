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

# Initialize bot and event loop
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Flask app for webhook
app = Flask(__name__)

@app.route(f"/{API_TOKEN}", methods=["POST"])
def webhook():
    """Handles incoming Telegram updates."""
    try:
        update = request.get_json()
        if update:
            async def process_update():
                telegram_update = telebot.types.Update.de_json(update)
                await bot.process_new_updates([telegram_update])

            loop.run_until_complete(process_update())
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    """Root endpoint"""
    return "Telegram bot is running!", 200

@app.route("/health")
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

def set_webhook():
    """Sets the Telegram webhook manually."""
    async def setup_webhook():
        await bot.remove_webhook()
        success = await bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}", timeout=60)
        if success:
            logger.info("Webhook set successfully")
        else:
            logger.error("Failed to set webhook")
        return success

    return loop.run_until_complete(setup_webhook())

if __name__ == "__main__":
    try:
        # Set webhook before starting the server
        if set_webhook():
            logger.info(f"Starting Flask webhook server on port {PORT}...")
            app.run(host="0.0.0.0", port=PORT, debug=True, use_reloader=False)
        else:
            logger.error("Failed to set webhook, not starting server")
            exit(1)
    except Exception as e:
        logger.error(f"Startup error: {e}")
        exit(1)
    finally:
        # Clean up
        try:
            loop.close()
        except:
            pass