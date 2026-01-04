import os
import logging
import asyncio
from flask import Flask, request
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Update
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "Telegram bot is running", 200

@app.route(f"/{API_TOKEN}", methods=["POST"])
def telegram_webhook():
    json_data = request.get_json()
    update = Update.de_json(json_data)
    asyncio.get_event_loop().create_task(bot.process_new_updates([update]))
    return "OK", 200