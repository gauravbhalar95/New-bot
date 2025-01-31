import os

# Telegram Bot Configuration
API_TOKEN = os.getenv("BOT_TOKEN")  # Your Telegram bot token
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Webhook URL for Telegram

# Server Configuration
PORT = int(os.getenv("PORT", 8080))  # Default port 8080

# Download Settings
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)  # Ensure the directory exists

# Cookie File (for Instagram & other sites requiring authentication)
COOKIES_FILE = "cookies.txt"

# Supported Domains
SUPPORTED_DOMAINS = [
    "youtube.com", "youtu.be", "instagram.com", "x.com",
    "facebook.com", "xvideos.com", "xnxx.com", "xhamster.com", "pornhub.com"
]

# Worker Settings
MAX_THREADS = 4  # Number of concurrent download threads
