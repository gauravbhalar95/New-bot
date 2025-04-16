import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MAX_WORKERS = "3"

API_TOKEN = os.getenv("BOT_TOKEN")  # Get from @BotFather

DROPBOX_ACCESS_TOKEN = "sl.u.AFrLQw3SJjUUsB1tx1Eit9GAJWHhkGiIn3uitzn7jcJ00eeHosIX5Bu6h27Zm_tF0M6kaEjc3Boz0uaZiAatsu8P5eTYnrVJsL3ilG3ivZX8CAMG_buoFQoer7eZl7gL6TEQ_8dOgSpuU2hRlTpC93P26bHghZQmoU_1QfVNND4uM3yCs31LcWTRf9XBpLtfNE6dsJGe-XMBjVLeRQk0xJg4TxdHbs-8T7ge6soZDngJZRdloFt8W3kDVfujnngFeivYEiZjSrgOd6yewzH8iiSqoynYnbgJUNOdP2GcBjLBZnp_LMajHFTQZyT3QF98gz67neOo0W9lncDOIFppdWkHwj2l4YY1pvyRtgIik3Hx6hmNphcPwoA8nfykQW1YYHEcusHZ-3yOxnrp9G1F_m-NTCdYAfmg1jV0k3vZn8QimFutfcwxpVq5IniFqzD1sLj0F2AsusLXpO87UVyOKtE1NgDRTgntjfT8AWBlviUU7fLgKhRiyVB5qsMfPQ84csN8Ozvct8nD4YsbRQMbMDqa8XWfzhXTiexlz_KUZaKGTevbAQjmZpXu-2b-zIdcVlQ2z3fuBeG8RxAdCKfaES5atVlUn_jeXDskr-znF_Qp_XIZ6I3At1zOnNJaDler2kF3U7OvJ2a4xeQ1rH89l-0ugFiwEjTIRVrjT2wxhVwE99XEcIWya18rjpkPYu4dXV_bC0SejWXGdZYz8NtV2RImdDi3D3dlw7JyVELdQRKJxckbPdI16XUpJw2R0Mjkv_lMFn1pRoDFUI4-VCqZAtiRSVAsnatto4iqlTke6ylJD-F2KdyOofWifuIrUfZycLt0_Jm8yXq4NmLqg5U8I0NnXlmkUkNPQoCHmlOVMjzEKoQO_JzAYxDLVejJr2fvKWF47v5j-BvXIGp-ZJNmjiJHrwHmEZG3AYQy6MmpH6TF4C85YhjOsW9hjXSgybhGZ6AHaC226zb01_kCe_LI2mp9Y3gMKU2HvDdRrGdYAsLahyHCfIHO7OTPzzyjiNSjRN-c9wSuhViT4W-W9ZwJytIQOU7Y8zguqGaVktwkMXpH-EqNIJuC-DsbWowa7ViGHDrBDaLjN6GT4BSrsUe-7ETt7rzohomVuAb8bItDkkQ-b1IgU3H-xTp4R_hAYIY0iNbqftii3NpWxvoep81zZo30tC3FtHyM2IiQev2gxGjVWM3ZXE-cO4mcYVda51dXWHd3TSKm7iQ0-t3qcD3C5nrCsb2RJoHcHNFdV3_1iVuKyGNM-4GmyZMAD7HcYV9jDc451VVktGiLMBtJ01JyPSN-TB5HZWD87mBhmdNS_CnvGg"

RAPIDAPI_KEY = "425e3f1022mshd7d4a2d9b3b0136p1fe9b1jsn0bd8321421c7"
RAPIDAPI_HOST = "instagram-downloader-download-instagram-stories-videos4.p.rapidapi.com"

MEGA_EMAIL = "gauravbhalara95@gmail.com" # Will be updated dynamically
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
TEMP_DIR = "TEMP_DIR"
os.makedirs(TEMP_DIR, exist_ok=True)

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