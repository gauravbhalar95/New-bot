import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")  # Get from @BotFather

# Instagram authentication settings
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")  # Set this in your environment
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")  # Set this in your environment

# Webhook URL for deployment
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Server Port (default: 8080)
PORT = int(os.getenv("PORT", 8080))

# Download directory
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Cookies file for authenticated downloads
X_FILE = "x.txt"
YOUTUBE_FILE = "youtube_cookies.txt"
INSTAGRAM_FILE = "Instagram_cookies.txt"

# Supported video platforms
SUPPORTED_DOMAINS = [
    "youtube.com", "youtu.be", "instagram.com", "x.com",
    "facebook.com", "xvideos.com", "xnxx.com", "xhamster.com", "pornhub.com"
]

# Telegram file size limit (2GB)
TELEGRAM_FILE_LIMIT = 100 * 1024 * 1024 # 2GB in bytes

MAX_FILE_SIZE = 100 * 1024 * 1024  # 50 MB limit