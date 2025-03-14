import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")  # Get from @BotFather

DROPBOX_ACCESS_TOKEN = "sl.u.AFl-2AZPoSgED9fTi1f_t0Zzt2zS9l32lMTqvwQHxSL3_NYgE8iL-De8fGNZ0IVIwOdGCfK0cyhCd_iKQ4O2GoEazPNh0VJlHxX8dDEUKK4ALf9sTtyH73xjIbTvIiNiEbVjBl0U-t8wuIAZUsSf3h3AKXlDOpf3cOrCkKnMr69gikj0APa4jtMn-DnD-Dpf5tvCw3fEl43iflC9N-YUxf1VQAKqtl0Len8EY4kWpmERMEcIQxsnS4caKU0eBzm91g6EXoxIzN9533_746ll_HKzGJvqfo03pR44xLSjpRngALLTNLDmgOYBsUpovUsFEDaBxC0MiB49Nb4ED2_WpmK8ag9R1W45NUJqYOJ-LmMp_4rF3mS1yNQTaficEuVZekcA5gaTQkUkT6aSAQ7NHE6_4Bm1_r8r9Bqtqw4Sq0hlwvydY9u8Q3QaQfsNDIYIVPLjNdLlK33ztxzOpdGoKAhEkcrVlg8TjIaZY_J9U-XVALaidsqJa-2EvtyoCVKHrqs7Gvz6BtMeIkYyU7cTsrSmFHG5di_-qcS21CAkCZcfi3xVpLR-XBTjxNOHWG6CHTXoEpXheucI07CrO1TGWNDC4ew52boxmB2EVm0cf9STbbokYyXwGqaNvTMd0LZ2QMH2CReSu9DWu0JxoMN2iiM80c3czIx8skk589KkqgFcNalpUgDIaakxX45uYCXUfn2Pa9bzw_9aCEyKCfEi9iaXtdBYaX8YIUkqUNPtKEqTnLGT_Qb5WBNUz0O8wpObWuhwQr6-j-J_C6HK_gBWBY_ivMVOxP5_kQQG_4TbCIrDLrZdY_rdvbGTVWNLFdTRIVjjQnXbLikjsTgcfk5D9ZOU_zgWdOjyE9UDTAw4MfQQXwniCMcm54D1KLjU7OQ1T6Q7lJ1yT3Lw0UyhSzWQVaooj8ROugsjs6Iv5a0z5R2DzCqyWQuUNNOZZBvtt34-WExuMDnrRMOxzotg5S52nPrHh_Bz401DcfsiBEc8vgF2LfpkkYnWZHvvCGvFEZjJVmfV3p6JY8K-3e7Cz2mlrhhV5clMK1erMFIz5ac9FC5sKxf-U1INNXLeg-RqkNZelJ2NgfLBl6LdoKdqQKkYBcm1APKc7fG22m9H7hqmVa7TLV6BS86jzN97IFwpO5RFJkbt1Oo_qG89bpj-tCZEEc_FJKON3RrbmCDeBLMO3gtIHX7BzgpnPTJdR7ZKXhNQ4oVFH1uIdHox0NZMS_bsbT46-MeGp7Y_t1HIpKaosKEXFPOPhLbieQy0604JpsBxRZZTjhWrrfXBhPcV0jW_Y4K58BCc9AzjFk7R9TKRIk9x9A"

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
MAX_FILE_SIZE_MB = 2 * 1024 * 1024 * 1024 # 2GB in bytes

TELEGRAM_FILE_LIMIT = 2 * 1024 * 1024 * 1024 # 50 MB limit