import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MAX_WORKERS = "3"

API_TOKEN = os.getenv("BOT_TOKEN")  # Get from @BotFather
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

INSTAGRAM_PASSWORD = "GAURAV74$"
INSTAGRAM_USERNAME = "top_deals_station"

DROPBOX_ACCESS_TOKEN = "sl.u.AFotWNB6b2z1nQBVdl3GHCweY7ZKrhk8BxN0ywjAmJO-4WA8zS-optwilzDWqroBx11WiYgf9GCSJtKP1obaSHQctblM1zRLADGbk5RmE2euiSqVO7fQZgRt3YHIqID2__vNkmOLHaxiv4usTH-kUO_UBMgMRXky_ELyvRu9N2B5z7J0Ozao54xGkJHPDxErubQst8Ga9SMzXoE2_BtHOOTTiH6Kfd5Xmsv4yVr-vh2ML_4U0XJ-MoWsfvmleb26WyC4HQDfnEsr-w3bXBWQtRZuRS8NYeWg0kNuY-OP6ewfeMg5CA7y69Z-bNntMmVdI4ozV66E0lS_2NGV6CnDlBjDDyf70eju68wxPWatFUjmx2ysZBImj1LOghdgmhJ4bZP8e6mkb7EWahKUX2cCND_fQfB1MNDzGyy3OfswemR3xU42w6pu6BXUtJ-gwYE_yrlh5mRY90A1fhT-2XKezfJCXYBHtdEx665sJ5mZe8Emzagz3QWo-hMO4_Jaeo2a4c1VXr2Kug8OPIyMCszCyjuZZrvPfVQmFvOD00r6gMoaMZApB5znB9var3KEpeUz7LaGeFxEitv5NRnXieH8uisSQl8d8DyS9Z9KUFl7LgLUTu2TgsW2kExSn6bCEmN9p3J2vNkfqQ_4HBTBSuq1uFX4PmyvM2C5dcKhxNCICbS_GXAM7q8BZAdCAW60OexGZuvSuClvSqZzO64_fP3YQQQCAiZwM9VddOvzxgwwO-dT-_le8u54krSC-PPEyXqfsfY3uMuoC1kL3s6thTThiliTTzRAYy55kdxc4xW9K4-RX2WYFNwanhFWw0Oqev8JkEVe5Nf1IZRpNAl4IVvEO8S4nfNf_qPDpfOHMf6Q5GrEmrAgY0GaFcLGpcceZwHV9HkgL7UufsnVu2-vf69sFYuxAAH0GbaXSbkd8h-OLscYR1wz0GXB-SJoeaRqvbsuA33FEIS0rvoHpEdMbwa3pYYpWazcqn4pSjE1UaRMlfCLIRQR5i8p1e5t5_-tuZyEHChIK32eZQu-BiCRG4QYHIEvt-LuDCYmDVsb6GgservoiFvyqlJ-z_yOLZT1IupWVvzwECVqJSrts-FCwy0qrvFYzHSqbHUqG3cXOTv3G75Nx18388bgnIpfnIsuBAWzvEizWFlgsAbs4WYZME4milNvbKWnquO1EmX7Eyw93TJwCoU9uxMBQQyKXdUzSsSkVlAR6Sx6aFwpr_0yvVBHmKkoepuR5yNEFeZ7K-X32r5WethxvmZ7Na4DEHDW7P1gvReXiELnoT5KBlw_DK0ScC7jye_DXikPteNeBtw3Slq7aA"
DROPBOX_APP_SECRET = "i34g2leylb8txhv"
DROPBOX_APP_KEY = "1k435aevlnbnngz"
DROPBOX_REFRESH_TOKEN = "bHxlbNdZW6YAAAAAAAAAVrNK7IOuC9klu7koUrJqKl0"

RAPIDAPI_KEY = "425e3f1022mshd7d4a2d9b3b0136p1fe9b1jsn0bd8321421c7"
RAPIDAPI_HOST = "instagram-downloader-download-instagram-stories-videos4.p.rapidapi.com"


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