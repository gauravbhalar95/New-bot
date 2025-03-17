import os
import logging
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

from quart import Quart, request
import telebot
import asyncio

app = Quart(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
async def webhook():
    data = await request.stream.read()
    bot.process_new_updates([telebot.types.Update.de_json(data.decode("utf-8"))])
    return "OK", 200

@app.route('/')
async def set_webhook():
    bot.remove_webhook()
    await asyncio.to_thread(bot.set_webhook, url=WEBHOOK_URL + '/' + API_TOKEN, timeout=60)
    return "Webhook set", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)