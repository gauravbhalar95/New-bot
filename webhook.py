from flask import Flask, request
from telebot import types
import os
from config import API_TOKEN, WEBHOOK_URL

app = Flask(__name__)

PORT = int(os.getenv("PORT", 8080))  # Use environment variable for port

@app.route('/' + API_TOKEN, methods=['POST'])
def webhook():
    from bot import bot  # Import bot instance inside the function to avoid circular import
    bot.process_new_updates([types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

@app.route('/')
def set_webhook():
    from bot import bot
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}", timeout=60)
    return "Webhook set", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)