import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MAX_WORKERS = "3"

API_TOKEN = os.getenv("BOT_TOKEN")  # Get from @BotFather

DROPBOX_ACCESS_TOKEN = "sl.u.AFqjS1Ayb-fqzoDhK5zULKoSuOJOGlKUmt_xTV9GZJIJvJqax8uZfGB6z0nN5Q0V9v_s6pjeCmm4puvHpRKaJdkcVTp95iGAQTRvu5vVWpwRNClcD836nelSg1GsMmmMcEyWZwdJGBblaQY61I4hEA3Gh4xHwAUT7Tj1zhY8-evIW3wjEoxXnKk2xipT7kHtNW3S4TbsiZK9uf5A5VRHZcScn-Yx8kX4b1uvIEddTB7OkMAnEFkRUx0xJq7RJgA5F8mZLE_QBiw5Od4xkLP2g2GmNReAit7Lm2AEhU53yINbyWW1dTBlWVEQH3QhYlzeWBwJSotkRQ9xyACB824LYOA70NH7u39orXlkGa8hFxDY3dqcMM8VQUx_ih5w05tTpFl5sFXD_qdgPi_syc-guiI9lFFAiAaTf3U9x_ad49Oco2hBwRdJ_3eieSa2MedlO5g2HOcJxSg_jYZRqvfQzNtTd_bK_umEU5jszT1WtZImQugODFPaFNYDiqXU6iGbNT3MTkrPOxgU6H8PquxInYKgs0jlj0YHhHkzvUksDZqg02FFL0_Og3t5ZYhqtcHTJCI_k1mxYnu8VkpKtvjUtD46_m4F-5H2jLXgIVr8gshosR4sV7YYrtoslBX6qHBvxyCRJpqKSbr7xjUGFErM5TAPYRx92Namh2kiY6C7bHn6XgiUg99qMvSSFpoXHfAal-SWgUGfugujptjiObfd3JnelY_eXZmypn8mngu0R5sQAR7NQFrnWMs7BePpnj0ikiuLLOGm3cxR_rTmqX0lACfi_sFwWfHxnhutoZKassdgsjjMM0JdxQWTjPYGp1HcJrAUgJ_bRuIbMwxdye1-RC0_xsJ7loVPWdOhC8bhhp2Iqw49f1CkphXjgSR5UQFelbV9sHX6joACfZ2R3WkPHL0lRy7e7jrwyd_ZcA46T3k0Csm3cD19Hn4xxUsy649PaTOnzwns1IjTwtDpoaoCCUuwwhHZQWNWMk0H5PpsdTtDuo7ZFVZJlmFN8VacXOcoe1Elj0dzeri6g_tnc-zBXhNOVa2hhv0-RMCR8DcA335zSUlO6lSf2T9zJS02YL0x5ikMV3EiGmnFM1yFzW0IFku2SBY1Z0TeB04mmyaIvUXEZUTd9pMgMv-bUSy5oI_OySBhN3ZT-_bgFR5-Si5C1DdcrUUBols14SGFRmFUYhloqYKzmB1OcQYL39HIUcaULYiPuPqjjPb4MPiBkGWPrb9jz19pSYQ_z4M5-OJtGBV5i1k6c1JpAEvT4Qn9yQMp2cAN4BGcXdIodzgLLJiGh1Hcgt-kmZahc99kud8B2a2qPA"

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