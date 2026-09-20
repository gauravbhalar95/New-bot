import asyncio
import logging
import threading
from concurrent.futures import TimeoutError as FutureTimeoutError

from flask import Flask, jsonify, request
import telebot

from bot import bot, main as start_bot_tasks
from config import API_TOKEN, WEBHOOK_URL, WEBHOOK_SECRET, PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

WEBHOOK_ENDPOINT = "/telegram-webhook"
FULL_WEBHOOK_URL = f"{WEBHOOK_URL}{WEBHOOK_ENDPOINT}"

_loop = asyncio.new_event_loop()
_loop_ready = threading.Event()


def run_async_loop():
    asyncio.set_event_loop(_loop)
    _loop.run_until_complete(start_bot_tasks())
    _loop.run_until_complete(set_webhook())
    _loop_ready.set()
    _loop.run_forever()


async def set_webhook():
    info = await bot.get_webhook_info()
    if info.url == FULL_WEBHOOK_URL:
        logger.info("Telegram webhook already configured.")
        return

    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(0.5)

    ok = await bot.set_webhook(
        url=FULL_WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET,
        max_connections=20,
    )
    if not ok:
        raise RuntimeError("Telegram setWebhook returned false")

    logger.info("Telegram webhook configured: %s", FULL_WEBHOOK_URL)


@app.route("/", methods=["GET"])
def home():
    return "Telegram bot is running", 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


@app.route(WEBHOOK_ENDPOINT, methods=["POST"])
def telegram_webhook():
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        return jsonify({"error": "unauthorized"}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "invalid update"}), 400

    try:
        update = telebot.types.Update.de_json(data)
        future = asyncio.run_coroutine_threadsafe(
            bot.process_new_updates([update]),
            _loop,
        )
        future.result(timeout=25)
        return jsonify({"ok": True}), 200
    except FutureTimeoutError:
        logger.warning("Update processing exceeded webhook timeout")
        return jsonify({"ok": True}), 200
    except Exception:
        logger.exception("Webhook update processing failed")
        return jsonify({"error": "processing failed"}), 500


if __name__ == "__main__":
    thread = threading.Thread(target=run_async_loop, daemon=True)
    thread.start()

    if not _loop_ready.wait(timeout=30):
        raise RuntimeError("Async bot loop failed to start")

    logger.info("Starting Flask server on port %s", PORT)
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False,
        threaded=True,
    )
