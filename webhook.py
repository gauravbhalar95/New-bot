import logging
import traceback

from quart import Quart, jsonify, request
import telebot

# Keep startup errors visible in Koyeb logs. Importing bot loads all handlers
# and can fail before Quart starts serving requests.
try:
    from bot import bot, start_background_tasks
    from config import WEBHOOK_SECRET, PORT
except Exception:
    logging.basicConfig(level=logging.INFO)
    logging.exception("FATAL: application import/startup failed")
    traceback.print_exc()
    raise

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Quart(__name__)

WEBHOOK_ENDPOINT = "/telegram-webhook"


@app.before_serving
async def startup():
    logger.info("Starting async background tasks...")
    app.background_tasks = await start_background_tasks()


@app.after_serving
async def shutdown():
    logger.info("Stopping async background tasks...")
    for task in getattr(app, "background_tasks", []):
        task.cancel()


@app.get("/")
async def home():
    return "Telegram bot is running", 200


@app.get("/health")
async def health():
    return jsonify({"status": "healthy"}), 200


@app.post("/webhook")
@app.post(WEBHOOK_ENDPOINT)
async def telegram_webhook():
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        return jsonify({"error": "unauthorized"}), 403

    data = await request.get_json(silent=True)

    if not data:
        return jsonify({"error": "invalid update"}), 400

    try:
        update = telebot.types.Update.de_json(data)
        await bot.process_new_updates([update])
        return jsonify({"ok": True}), 200

    except Exception:
        logger.exception("Webhook update processing failed")
        return jsonify({"error": "processing failed"}), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
    )
