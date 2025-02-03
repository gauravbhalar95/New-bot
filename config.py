import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram Bot Token
API_TOKEN = os.getenv("BOT_TOKEN")

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


DOWNLOAD_POST = "downloads/post"
os.makedirs(DOWNLOAD_POST, exist_ok=True)

DOWNLOAD_STORY = "downloads/story"
os.makedirs(DOWNLOAD_STORY, exist_ok=True)


# Cookies file for authenticated downloads
COOKIES_FILE = "cookies.txt"

# Supported video platforms
SUPPORTED_DOMAINS = [
    "youtube.com", "youtu.be", "instagram.com", "x.com",
    "facebook.com", "xvideos.com", "xnxx.com", "xhamster.com", "pornhub.com"
]

# Telegram file size limit (2GB)
TELEGRAM_FILE_LIMIT = 2 * 1024 * 1024 * 1024  # 2GB in bytes
