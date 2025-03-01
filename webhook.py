import os
import logging
from flask import Flask, request, jsonify
from telebot import types
from dotenv import load_dotenv
from bot import bot  # Ensure bot instance is correctly imported
from config import API_TOKEN, WEBHOOK_URL, PORT
from utils.logger import setup_logging

# Load environment variables
load_dotenv()



logger = setup_logging

def create_app():
    app = Flask(__name__)

    @app.route(f"/{API_TOKEN}", methods=["POST"])
    def webhook():
        try:
            update = types.Update.de_json(request.stream.read().decode("utf-8"))
            bot.process_new_updates([update])
            return jsonify({"status": "success"}), 200
        except Exception as e:
            logger.error(f"Error processing update: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/set_webhook", methods=["GET"])
    def set_webhook():
        bot.remove_webhook()
        success = bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}")
        if success:
            return jsonify({"message": "Webhook set successfully"}), 200
        else:
            return jsonify({"error": "Failed to set webhook"}), 500

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=PORT, debug=True)