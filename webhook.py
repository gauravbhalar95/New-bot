import os
import telebot
from telebot.async_telebot import AsyncTeleBot
from flask import Flask, request
import asyncio

# Load environment variables
API_TOKEN = os.getenv("API_TOKEN")  # Telegram bot token
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-app.koyeb.app

# Create async TeleBot instance
bot = AsyncTeleBot(API_TOKEN)
app = Flask(__name__)

# Route to receive Telegram updates via webhook
@app.route(f'/{API_TOKEN}', methods=['POST'])
async def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    await bot.process_new_updates([update])
    return '', 200

# Route to confirm app is running
@app.route('/')
def home():
    return 'Telegram bot webhook is running!'

# Define command handler
@bot.message_handler(commands=['start'])
async def start_handler(message):
    await bot.send_message(message.chat.id, "Welcome! Your bot is working via webhook.")

# Function to set webhook URL
async def set_webhook():
    await bot.remove_webhook()
    await bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}")
    print(f"Webhook set to: {WEBHOOK_URL}/{API_TOKEN}")

# Start the app using Hypercorn to support asyncio
if __name__ == "__main__":
    import logging
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    logging.basicConfig(level=logging.INFO)

    # Configure Hypercorn for Flask app
    config = Config()
    config.bind = ["0.0.0.0:8080"]

    # Start event loop
    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_webhook())
    loop.run_until_complete(serve(app, config))