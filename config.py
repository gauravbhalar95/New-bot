import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")  # Get from @BotFather

DROPBOX_ACCESS_TOKEN = "sl.u.AFowCMighjSPvs2_4KvyPdhfsFbDcVafkVbGnmuUxtDl7cSkEE7Yt2KZsxTuQsR9XmtP1GBCega15y1-zeigb7xI7-JaQ2bTrlFULe4KneE_DRGxZOzNrhvj-YshLqcXQ9YKMezFRBXff4-UI0P1CXOWwzs1Lu_w1CJebZURma0ztt3uP7z5ULTdq9Qhy3prZD-fu_8CNbEMyxo_6RY3p5LlOIjDf53ZL8OPA-aEvA1Bwr5NFbzCK8kDGTFeGisI4gxut8oO_cJ_c8C9ZWofzQX2kJ4hboV7mH5NxQifsXHYT49GTMk5w21KpMMSm71iKSOs6fFU50G_j7tKZpK2-9qMqSLNDBxc89GR6_YbGBDVMerhR2_8sqUkOUgt-jEe08B-yEFpAfnao-c5J54E2HGpqA8STZDP7L7VwL8kuDpYQEWhf3wESWq7xe_-2Gs7VF-UDWcUrABj5Fby9KHPkDGZOzzvwX-TM8u5nt-WBQG4GxPIF4m10SlZWj99DPTxIpX3HK2tE5RAQ0xVmcsHRJC96QP97Og1JMvZEWUGZLUkGaSF0In32zx3KoAs_YPvekdY74J_dV-5Mtbjrp9oSllQdAxElex4eOPmS4JE-R5jgmu8Ht6zpL7lbKx1NpyOhTgpSteT4q1vj1_0HKla49qHiaof_CPmAqNl-rEmTxlF-buJ71kysHOvu5i8LXLFnJ5m7fWqJKaW-sa1lO20lRWBy416gBZa1eq1UjuUIx50_xmw8iEGDOOy37fuN3MrJe_ku9QB2U2NlS2IYEvOZ-KS2IZOe9nXnkPZ4RDTWLiiKc2lTEKbUATGGBso-lluCAXnpb29JBBsdfQ_JYJhdeBNE7KlQMbIZWsdmQiLnNvhzNdsi88Yph15awbqLxILG3mFnaEHyD4uhaEA_hcVma_le_3cuvQh8V4gBIwE8CGUwO7I2J1pL4yROcMVlviDJu93_vQptweOtM_pjDem0dr0ztSGam13vvYo0Dz9YhVwLoBq92Jahy9pd1Oipya2Z1XTM7pKzYKRvRXDC_tJTgTCejfHW8xwsiWYMEws2jvedRA9T3hghiyZV4tqmXaSToPUWX_0hFxRhDSB7ACBIBOyljq6mc7_QKpkijZ4zO31OB-wcDoG7MWDCC1y05FsHZUAixjdsHKaltJcfNuwAvOjn8nlsqUbXAjH_F7xt99osQY0BhP4D09TCDxXTJw5EZUDxSuEhZLLZ1bwnF5wml53m_EiMlwEEnHrWIgZJ_KeeDZxr0VmklJkL5LGpaq_OkTju0WOc38LwtK-NJSB6w_Zyc3JxQSJhtSOfS5QeCI78w"

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