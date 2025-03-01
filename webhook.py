import os
import logging
import asyncio
from quart import Quart, request, jsonify
from dotenv import load_dotenv
from telebot.async_telebot import AsyncTeleBot
from config import API_TOKEN, WEBHOOK_URL, PORT
from utils.logger import setup_logging

# Load environment variables
load_dotenv()

logger = setup_logging(logging.INFO)

# Initialize bot with async support
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")

app = Quart(__name__)

@app.route(f"/{API_TOKEN}", methods=["POST"])
async def webhook():
    try:
        data = await request.get_data()
        update = types.Update.de_json(data.decode("utf-8"))
        await bot.process_new_updates([update])
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/set_webhook", methods=["GET"])
async def set_webhook():
    await bot.remove_webhook()
    success = await bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}")
    if success:
        return jsonify({"message": "Webhook set successfully"}), 200
    else:
        return jsonify({"error": "Failed to set webhook"}), 500

async def run():
    """Run the Flask app asynchronously."""
    await app.run_task(host="0.0.0.0", port=PORT, debug=True)

if __name__ == "__main__":
    asyncio.run(run())