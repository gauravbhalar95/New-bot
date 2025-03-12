import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")  # Get from @BotFather

RAPIDAPI_KEY = "425e3f1022mshd7d4a2d9b3b0136p1fe9b1jsn0bd8321421c7"
RAPIDAPI_HOST = "instagram-downloader-download-instagram-stories-videos4.p.rapidapi.com"

MEGA_USERNAME = None  # Will be updated dynamically
MEGA_PASSWORD = None  # Will be updated dynamically


# Instagram authentication settings
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")  # Set this in your environment
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")  # Set this in your environment

# Webhook URL for deployment
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Server Port (default: 8080)
PORT = int(os.getenv("PORT", 9000))

# Download directory
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Download directory
DOWNLOAD_DIR2 = "downloads/post"
os.makedirs(DOWNLOAD_DIR2, exist_ok=True)

# Download directory
DOWNLOAD_DIR3 = "downloads/story"
os.makedirs(DOWNLOAD_DIR3, exist_ok=True)

# Cookies file for authenticated downloads
X_FILE = "x.txt"
YOUTUBE_FILE = "youtube_cookies.txt"
INSTAGRAM_FILE = "instagram_cookies.txt"
COOKIES_FILE = "cookies.txt"
FACEBOOK_FILE = "facebook.txt"

# Supported video platforms
SUPPORTED_DOMAINS = [
    "youtube.com", "youtu.be", "facebook.com", "instagram.com", "x.com",
    "facebook.com", "xvideos.com", "xnxx.com", "xhamster.com", "pornhub.com"
]

# Telegram file size limit (2GB)
MAX_FILE_SIZE_MB = 50 * 1024 * 1024 # 2GB in bytes

TELEGRAM_FILE_LIMIT = 50 * 1024 * 1024 # 50 MB limit