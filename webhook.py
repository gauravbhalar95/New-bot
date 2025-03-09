import os
import logging
import asyncio
import aiohttp
from flask import Flask, request, jsonify, render_template
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
app = Flask(__name__, template_folder="templates")  # Set templates folder

@app.route("/", methods=["GET"])
def home():
    """Simple route to check if the server is running."""
    return jsonify({"status": "running", "message": "Webhook server is up!"})

@app.route("/dashboard", methods=["GET"])
def dashboard():
    """Serves the dashboard HTML page."""
    return render_template("dashboard.html", webhook_url=WEBHOOK_URL, api_token=API_TOKEN)

@app.route('/' + API_TOKEN, methods=['POST'])
async def webhook():
    """Handles incoming Telegram updates asynchronously."""
    try:
        data = request.get_data().decode("utf-8")
        logger.info(f"Received update: {data}")  # Log incoming data
        update = telebot.types.Update.de_json(data)
        await bot.process_new_updates([update])
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return jsonify({"error": str(e)}), 500

async def set_webhook():
    """Asynchronously sets the Telegram webhook."""
    session = aiohttp.ClientSession()
    try:
        await bot.remove_webhook()
        success = await bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}")
        if success:
            logger.info(f"Webhook set successfully at {WEBHOOK_URL}/{API_TOKEN}")
        else:
            logger.error("Failed to set webhook")
    except Exception as e:
        logger.error(f"Webhook setup failed: {e}")
    finally:
        await session.close()

# Gunicorn will use this app instance
if __name__ != "__main__":
    logger.info("Flask app initialized, ready for Gunicorn.")