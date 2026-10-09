import asyncio
import logging
import traceback
from pathlib import Path

from quart import Quart, jsonify, request
import telebot

# Keep startup errors visible in Koyeb logs. Importing bot loads all handlers
# and can fail before Quart starts serving requests.
try:
    from bot import bot, start_background_tasks
    from config import API_TOKEN, WEBHOOK_URL, WEBHOOK_SECRET, PORT, MINIAPP_URL
    from utils.instagram_oauth import (
        create_authorization_url,
        disconnect,
        finish_authorization,
        get_account,
    )
    from utils.telegram_webapp_auth import validate_init_data
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


def _miniapp_user_id() -> int:
    raw_init_data = request.headers.get("X-Telegram-Init-Data", "")
    user = validate_init_data(raw_init_data, API_TOKEN)
    return int(user["id"])


def resolve_telegram_webhook_url() -> str:
    """Accept either a public base URL or a full Telegram webhook URL."""
    if WEBHOOK_URL.endswith(("/webhook", "/telegram-webhook")):
        return WEBHOOK_URL
    return f"{WEBHOOK_URL}/telegram-webhook"


@app.before_serving
async def startup():
    logger.info("Configuring Telegram webhook...")
    telegram_webhook_url = resolve_telegram_webhook_url()

    if not telegram_webhook_url.startswith("https://"):
        raise RuntimeError("WEBHOOK_URL must use a public HTTPS URL")

    # Register the webhook here: without set_webhook(), Telegram will not send
    # incoming messages to this Quart application.
    webhook_set = await bot.set_webhook(
        url=telegram_webhook_url,
        secret_token=WEBHOOK_SECRET,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=False,
    )
    if not webhook_set:
        raise RuntimeError("Telegram rejected setWebhook; check BOT_TOKEN and WEBHOOK_URL")

    webhook_info = await bot.get_webhook_info()
    logger.info(
        "Telegram webhook active: url=%s pending_updates=%s last_error=%s",
        webhook_info.url,
        webhook_info.pending_update_count,
        webhook_info.last_error_message,
    )

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


@app.get("/miniapp")
async def miniapp():
    html_path = Path(__file__).resolve().parent / "webapp" / "index.html"
    return html_path.read_text(encoding="utf-8"), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/api/instagram/login")
async def instagram_login():
    try:
        user_id = _miniapp_user_id()
        return jsonify({"url": create_authorization_url(user_id)})
    except Exception as exc:
        logger.warning("Instagram Mini App login initialization failed: %s", exc)
        return jsonify({"error": str(exc)}), 400


@app.get("/instagram/callback")
async def instagram_callback():
    error = request.args.get("error")
    if error:
        return (
            f"<script>location.replace({MINIAPP_URL!r} + '?auth_error=' + encodeURIComponent({error!r}))</script>",
            200,
            {"Content-Type": "text/html; charset=utf-8"},
        )

    code = request.args.get("code")
    state = request.args.get("state")
    if not code or not state:
        return "Instagram authorization response is incomplete.", 400

    try:
        await asyncio.to_thread(finish_authorization, state, code)
        return (
            f"<script>location.replace({MINIAPP_URL!r} + '?instagram=connected')</script>",
            200,
            {"Content-Type": "text/html; charset=utf-8"},
        )
    except Exception as exc:
        logger.warning("Instagram OAuth callback failed: %s", exc, exc_info=True)
        return (
            f"<script>location.replace({MINIAPP_URL!r} + '?auth_error=' + encodeURIComponent({str(exc)!r}))</script>",
            200,
            {"Content-Type": "text/html; charset=utf-8"},
        )


@app.get("/api/instagram/status")
async def instagram_status():
    try:
        user_id = _miniapp_user_id()
        account = get_account(user_id)
        if not account:
            return jsonify({"connected": False})
        return jsonify({
            "connected": True,
            "username": account.get("username"),
            "user_id": account.get("user_id"),
            "expires_at": account.get("expires_at"),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 401


@app.post("/api/instagram/logout")
async def instagram_logout():
    try:
        user_id = _miniapp_user_id()
        disconnect(user_id)
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 401



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
