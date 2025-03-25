import os
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import telebot
from telebot.async_telebot import AsyncTeleBot
from config import API_TOKEN, WEBHOOK_URL, PORT

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")

# Flask app for webhook & HTML page
app = Flask(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
async def webhook():
    """Handles incoming Telegram updates asynchronously."""
    try:
        data = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(data)
        await bot.process_new_updates([update])  # Use await for async processing
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def set_webhook():
    """Sets the Telegram webhook."""
    try:
        bot.remove_webhook()
        success = bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}", timeout=60)
        return "Webhook set successfully" if success else "Failed to set webhook", 200 if success else 500
    except Exception as e:
        logger.error(f"Webhook setup failed: {e}")
        return f"Error: {str(e)}", 500

@app.route('/download')
def download_page():
    """Serves an HTML page with the video download link."""
    video_url = request.args.get('video_url')
    
    if not video_url:
        return "❌ No video URL provided!", 400
    
    return render_template('download.html', video_url=video_url)

if __name__ == '__main__':
    logger.info(f"Starting Flask webhook server on port {PORT}...")
    app.run(host='0.0.0.0', port=PORT)