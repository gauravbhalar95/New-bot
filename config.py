import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram Bot Token
API_TOKEN = os.getenv("BOT_TOKEN")

# Webhook URL for deployment
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Server Port (default: 8080)
PORT = int(os.getenv("PORT", 8080))

# Download directory
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Cookies file for authenticated downloads
COOKIES_FILE = "cookies.txt"

# Supported video platforms
SUPPORTED_DOMAINS = [
    "youtube.com", "youtu.be", "instagram.com", "x.com",
    "facebook.com", "xvideos.com", "xnxx.com", "xhamster.com", "pornhub.com"
]

# Telegram file size limit (2GB)
TELEGRAM_FILE_LIMIT = 2 * 1024 * 1024 * 1024  # 2GB in bytes
