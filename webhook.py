from flask import Flask, request
from telebot import types
from config import API_TOKEN, WEBHOOK_URL
from bot import bot

app = Flask(__name__)

@app.route(f"/{API_TOKEN}", methods=["POST"])
def webhook():
    """Receives Telegram updates and processes them."""
    try:
        bot.process_new_updates([types.Update.de_json(request.get_data().decode("utf-8"))])
        return "OK", 200
    except Exception as e:
        return str(e), 500

@app.route("/")
def set_webhook():
    """Sets the webhook for Telegram bot."""
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}", timeout=60)
    return "Webhook set", 200

if __name__ == "__main__":
    from waitress import serve  # Use production-ready server
    print("🚀 Starting webhook server on port 9000...")
    serve(app, host="0.0.0.0", port=9000)