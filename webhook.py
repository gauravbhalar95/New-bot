import os
from flask import Flask, request
from telebot import types
from config import API_TOKEN, WEBHOOK_URL
from bot import bot

# Fetch PORT dynamically
PORT = int(os.environ.get("PORT", 9000))

app = Flask(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
def webhook():
    bot.process_new_updates([types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

@app.route('/set_webhook')
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}")
    return "Webhook set successfully", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT)