import logging
from bot import bot, start_background_tasks  # Import the new function
from config import WEBHOOK_SECRET, PORT

from flask import Flask, jsonify, request
import telebot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

app = Flask(__name__)

WEBHOOK_ENDPOINT = "/telegram-webhook"


@app.route("/", methods=["GET"])
def home():

    return "Telegram bot is running", 200


@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "healthy"
    }), 200


@app.route(WEBHOOK_ENDPOINT, methods=["POST"])
def telegram_webhook():

    if (
        request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token"
        )
        != WEBHOOK_SECRET
    ):

        return jsonify({
            "error": "unauthorized"
        }), 403

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error": "invalid update"
        }), 400

    try:

        update = telebot.types.Update.de_json(
            data
        )

        bot.process_new_updates(
            [update]
        )

        return jsonify({
            "ok": True
        }), 200

    except Exception:

        logger.exception(
            "Webhook update processing failed"
        )

        return jsonify({
            "error": "processing failed"
        }), 500


# In webhook.py, modify the imports and the bottom block:

# ... (keep all your flask routes the same) ...

if __name__ == "__main__":
    logger.info("Starting background tasks...")
    start_background_tasks()  # Start the queue workers!

    logger.info("Starting Flask server on port %s", PORT)
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False,
        threaded=True,
    )
