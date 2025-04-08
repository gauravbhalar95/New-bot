import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MAX_WORKERS = "3"

API_TOKEN = os.getenv("BOT_TOKEN")  # Get from @BotFather

DROPBOX_ACCESS_TOKEN = "sl.u.AFrgeZpzL9NAuSKQUQiJdEq-Uk6yh_KrtiPCwkBuNOwskoOArEVvDlHfmlcCdOp_EH0-sx6GniCsSXii0uCxDCRwEnaOcIQjyUJurzxkUAa_tXqKM5yGMp8Imle0_cPUtaHPeO9ZVE1_maDD0CCFiXh-k1YWpW-LNwPZwXleUc_pIPOgAxLSpoU8z2eydVYleln0GCO31_rICBA7izuqPWlcp4AGthN97MsQcPiQzacaKyvnGpVJ79IewJAbvFbAL6FSb9ILpPF2okdVjPi4_jeKwiSZM-20xJWVJ9jNq3l5gqF88NkxEkk-7eMuCwFeWcEpXXRzOhstfFHuywLKBuaiKHnF0Vha3ylsXTWOaRoI6BVKSVSAYbHFTRqCxFw0bVp9T5tyio4jARRp7ha6_zqLMjHCOMA7HmNrov1909abwdcDNNjtz1yhogS8Y4TVss4L5eprFpQbWUP4gUkNea4_cpqCre9vImexLkvOQtaU2JByoPX6laBCmTJhmSs9iq9GEaZrhAxeUAnpwn9XyCN_tZKh297IXrxUT3w-4lZILj0ji_isnqmTHT6WeRtaCAciNq4AxCvCZ7e3wbUjh9lmiM6Rur2ShIy1IB0nwDjy_v8b1pyxMOzND6GBJfbpjuH_gVP34gSKXy8SGHbwvRlgxQivKguJChUqHX7ruYyKwNAlVIh1I-K9qdjbUg_RhzrPuqF-iD8hBok_72sat6hfJ0e6r2USbTVIhKSL5khNwozHxmgTqUL6bpkv82lF6YbvTyIVaQxXgdv-H64bPTv7LmwZREC11o1R8wPbXDEqII6jEJ8P-yb3x8e6aEziugnrhlOtVK3FFzXoNHLLv0bLDzxtkV6LAR0M5oDr9SP-R0esVmRx10Zw8vmG-hJFmENzRpAQS0Etccb9QLOAGO32fRYNPcvu2vJP48d9hHGUNXiE1VvQlYMtsTREC-vIShPnwuAf4GfJHKErqYbE5jvUPq0XP-F4sf6UIRBsjQcmJ-tDWynQ8_Bz6vqs4WsBbfziqnvGVHciQ6-C43dT9nJAtgbinS_HR7O89XqfmKXvxzJJseLCh1zqtW3n3zzESvlB519ddf5jnQD2JssS2MOX2ohsFKvstcSA-eoRY9CrlRofrGN8gMRieNlzFLLdUIfdRj6JUGftNc6_iIxQb6ht8D2Rej0ivvFOG-soR_9BvCVc2oQnQ_0xxcMkYYbYI02vsmdl_vFxScRrmiLEdDPe8g6YFdXF1J0ZVu8yzRDY44xbVxqKLQo752JxjC-wdsbN9x_0KnD6wO9uqaXE5hOv9YUwMNg-v-VJQw3GRYUYVg"

RAPIDAPI_KEY = "425e3f1022mshd7d4a2d9b3b0136p1fe9b1jsn0bd8321421c7"
RAPIDAPI_HOST = "instagram-downloader-download-instagram-stories-videos4.p.rapidapi.com"

MEGA_USERNAME = "gauravbhalara95@gmail.com" # Will be updated dynamically
MEGA_PASSWORD = "Gaurav74$"  # Will be updated dynamically


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
MAX_FILE_SIZE_MB = 2 * 1024 * 1024 * 1024 # 2GB in bytes

TELEGRAM_FILE_LIMIT = 2 * 1024 * 1024 * 1024 # 50 MB limit