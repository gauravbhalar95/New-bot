import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MAX_WORKERS = "3"

API_TOKEN = os.getenv("BOT_TOKEN")  # Get from @BotFather

DROPBOX_ACCESS_TOKEN = "sl.u.AFo1-AQiR80eePprFJua8hBpWvBrLr_0vKWKHd1whBOAM5MFXKPeDEyhofFfcR5le81075IFBb0J84jwjgBg_LWrsv-AWW-45QOyp7gvKnq7dT6ukpI_TrPDHnu4y1g9QD5O3OAfqLkENk2NLqocBx4P5GXrAe8WdJcHq8u39vCp2SYWPeZEeGEy47X7UATZyKH61DN1RvAKGnlazPgolQQ-2ihR-WaJpNKefx9bDqSr6aqane5CyqRSiLxZxae0FTXVUXtFDRywZYPKk80FEdh0MQQpA-bhIhqBNtKmWxatFZEitVCNxAM8f6I9TlaM-2FHEYAdJfnIfCsAz6WfsHMizH6twatKOtHWyY9VurcfT2htAgAHQrJYX4WLzp1VWH7HCSMnLHxY8Pi614dd4DEaPp7vsWUpUJAK-RtLtefvSLMGvh1JcJ_M6C60-Ra6hYcDfkXHkM3R3pWmsCRkzbkN6eF0mdJKs3jaxvuz61SDgwtNR0NmzTQ7WVFgECEPruxAJkBH9gAX7zbdoMxMnMKsV38WwthODeBeq7dCt0u7OzIakmbPJbTJvDAMcc6UIIZGUsEf6X6iSb4uiV9l3R_aKycE-Mlnv0_1SWwoAzGf74UUZ7OtZch6J0WaPpYIf_VnMaebgJ0FrecstmhQEaM5AADFkXodvjdRbkhO4x-0xSwAjc2yBT57lk78exGf0XOEAGr62RE0J7VM_sL7Ormo1XINkoUvzuCxnYg07nYoWlH8AVCoA3Kpo2n1FeFXY49W5nTq_8S3DCq-4GDwXwIA3ZeughGsETlPyRSVIvkYmGnhBR6xKjCZEs4B-Xf70OJFaQSt-3n_iOwpAH1M1vBNIKKkaYC8NNwb-Jk9p15CeDrYQ-DzKE53RvMATPZeuc1RBh2iEGyQAwuThMqpLXav6Juyqh1P4jpD9bJcWTlrnQD1e2GuaqN2tCNNqBwwEnFIQYhrVR2j3UISjuSkIdKWDNfazGk8w6zxmUCDh5TPm0s-DLxzIQMdjF6DwjzUFEuQGotN7Ywy9_KPxGitQUgXRkj_poVSPYS0xP7q6xyXPtM0t7CPI4THY62hSpea2GB8eeH9vyg4A92sgDxYBX1fcwORcyjoeXS0eAKGWVAHOIBePKPngCmhG_vpB4o7LsomFaNoG47uUkhahZ27OqbHu9pk3LyvhF8xLPZMbm3msx--kOdRFqPr-pDTbr7Qe4KLmNTvu-W-T0VAcTLwkFrhN9JJAK13b5ZAj0aVerWXWXoxqePfihBDut_21ZKJI7pd3KNy7ehYlPlQKmntLAdXdnTnWXTM9ZgnNR-b6F4gaA"

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