import os
import asyncio
import logging
from fastapi import FastAPI, Request
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

# FastAPI app for webhook
app = FastAPI()

@app.post(f'/{API_TOKEN}')
async def webhook(request: Request):
    """Handles incoming Telegram updates asynchronously."""
    try:
        data = await request.body()
        update = telebot.types.Update.de_json(data.decode("utf-8"))
        await bot.process_new_updates([update])
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return {"error": str(e)}

@app.get('/')
async def set_webhook():
    """Sets the Telegram webhook asynchronously."""
    try:
        await bot.remove_webhook()
        await bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}")
        return "Webhook set successfully"
    except Exception as e:
        logger.error(f"Webhook setup failed: {e}")
        return f"Error: {str(e)}"

async def start_bot():
    """Handles async setup for Telegram bot."""
    await bot.remove_webhook()
    await bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}")
    logger.info(f"Starting FastAPI webhook server on port {PORT}...")

if __name__ == '__main__':
    import uvicorn
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    uvicorn.run(app, host='0.0.0.0', port=PORT)