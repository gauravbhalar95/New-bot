import os
import asyncio
import logging

from flask import Flask, request, jsonify
import telebot

from telebot.async_telebot import AsyncTeleBot

from config import API_TOKEN, WEBHOOK_URL, PORT


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# ============================================================
# BOT
# ============================================================

bot = AsyncTeleBot(
    API_TOKEN,
    parse_mode="HTML"
)


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


# ============================================================
# WEBHOOK URL
# ============================================================

WEBHOOK_PATH = f"/{API_TOKEN}"
FULL_WEBHOOK_URL = f"{WEBHOOK_URL.rstrip('/')}/{API_TOKEN}"


# ============================================================
# WEBHOOK
# ============================================================

@app.route(
    WEBHOOK_PATH,
    methods=["POST"]
)
def webhook():

    try:

        data = request.get_json(
            silent=True
        )

        if not data:

            return jsonify({
                "status": "no data"
            }), 400

        update = telebot.types.Update.de_json(
            data
        )

        # Run async handler
        asyncio.run(
            bot.process_new_updates(
                [update]
            )
        )

        return jsonify({
            "status": "ok"
        }), 200

    except Exception as e:

        logger.error(
            f"Webhook error: {e}",
            exc_info=True
        )

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/")
def home():

    return (
        "Telegram bot is running!",
        200
    )


@app.route("/health")
def health():

    return jsonify({
        "status": "healthy"
    }), 200


# ============================================================
# SET WEBHOOK
# ============================================================

async def set_webhook():

    try:

        info = await bot.get_webhook_info()

        logger.info(
            f"Current webhook: {info.url}"
        )

        # Already correct
        if info.url == FULL_WEBHOOK_URL:

            logger.info(
                "Webhook already configured."
            )

            return

        # Remove old webhook first
        logger.info(
            "Removing old webhook..."
        )

        await bot.delete_webhook(
            drop_pending_updates=True
        )

        await asyncio.sleep(1)

        # Set new webhook
        logger.info(
            f"Setting webhook: "
            f"{FULL_WEBHOOK_URL}"
        )

        success = await bot.set_webhook(
            url=FULL_WEBHOOK_URL
        )

        if success:

            logger.info(
                "✅ Webhook set successfully."
            )

        else:

            logger.error(
                "❌ Failed to set webhook."
            )

    except Exception as e:

        logger.error(
            f"Webhook setup error: {e}",
            exc_info=True
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    logger.info(
        "Configuring Telegram webhook..."
    )

    asyncio.run(
        set_webhook()
    )

    logger.info(
        f"Starting Flask server "
        f"on port {PORT}..."
    )

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False
    )