from flask import Flask, request, jsonify
import os
import logging
from telebot import types
from config import API_TOKEN, WEBHOOK_URL
from bot import bot  

app = Flask(__name__)

# Enable logging
logging.basicConfig(level=logging.DEBUG)

@app.route('/' + API_TOKEN, methods=['POST'])
def webhook():
    try:
        json_data = request.stream.read().decode("utf-8")
        logging.debug(f"Received webhook: {json_data}")
        update = types.Update.de_json(json_data)
        bot.process_new_updates([update])
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logging.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/setwebhook')
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + '/' + API_TOKEN, timeout=60)
    return "Webhook set", 200

if __name__ == '__main__':
    PORT = int(os.getenv("PORT", 8080))  # Ensure PORT is set
    app.run(host='0.0.0.0', port=PORT)