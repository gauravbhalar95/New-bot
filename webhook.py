from flask import Flask, request
from telebot import types
from config import API_TOKEN, WEBHOOK_URL
from bot import bot

app = Flask(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
def webhook():
    try:
        bot.process_new_updates([types.Update.de_json(request.stream.read().decode("utf-8"))])
        return "OK", 200
    except Exception as e:
        return str(e), 500

@app.route('/')
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}", timeout=60)
    return "Webhook set", 200

if __name__ == "__main__":
    from waitress import serve  # Production server
    serve(app, host="0.0.0.0", port=9000)