import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")  # Get from @BotFather

DROPBOX_ACCESS_TOKEN = "sl.u.AFqQKT_66naHTZT5c_ya35tVvsFplL7IPEsxa3--D71NAMiSsrxfuM4FmuZC4CEQegZqWvOPvzHY9zaITrLM3O5qvQjDynej9IQGqrA1OVFR6xrBQ0FL38VA79D0xn75flu_v2LdKCzDLoH0eApo8YJShbPcMv98lwY7KzvIeqhMCw7X579Hr33c5AWBNO3RTlqWcvzYq0tJc-2CZT_E1GHDHVflm2-onaasHZPgBTWPscdAGzPaerLd2zWwRLI7oEvfHNwSDqJX-9iFFYNBjcjenwWViWs1updpMBOdOiKV4X73bPguG5mScMGkC0y-oUVXjQP5sXCex0eQXZWNcGIymLHgRIuKrZWelG_-YlUfOLoVLKnGbc3kNFJcG8dg66z0OqQj34j-clGV_iCUCmOLD5Dpbxe8QMiC-3NpcMgylHUgFOqkzBoBuyRRVl7wEUN4YWL_RIpQIMY0z3KFDiuUtZauTvUGzUVZOnRxAo341zvR0UUIvwv10joN5kY_Y2gXiOalzHcl8qH8LH6at-0Td95dJQ3E8T8s1fd9N3UxohgbWRZZHfsvADvBi_M4SwfRlFSWx_xO8FVPRxs_WulWzxoPKKdsfvACpZSqvv_OLD1e23l4Fev0ry-jB7Bq8uNnElXmerVq_Jr1lBYjjxWxjf-1WxxmELEJpwYax9d9xxaBR4xK1WV2XRu0ciI80H8z4cOjkRgx4Jp2MGMtxZfeKvlAclklfPXhmQsOkrdaClFzOIUcjhL3_Wv4t-sdeUIKYcjy0SErgfiUHdTiqVrzE4ME0ARYoF9xJorG83tsap424mufvL0capXQD-0aeBxXYqkQSjyR4c6FfXCR6xsOw_O3CQyTCrAMpIPvw9PVCqWxbEeo2mmPycogi-GMFhM_gKKcRO9e0XLxybHa3Xe7w5uS5QaXeQNYQcbt-L8HKfVfGP4LbCogcorvCOXIjZ7xjaHrK8_m6tr6m0_zeqqS0KF6XLhtfEQiu9ZPznSpG2uekYB0Nf-9coRSDm-9ssfz2xZwHmesh8Dt5kQzMOqwGQn6iB2vsC_ixDGUCtI6Q4cMjQtDlAeY14n5iu6P0_22f9rwxqtdbDpFOeI3-2Ip-AMyyzWsAytfGM8oo8gH6ZsCydFkYS_zgVDbdzzvqkG3XUW8IfpdeQ6hgEGrxHo6m95l_lDhbchv72SYrHp2ibDBC6F4pSHIL7fuMC5XpD5bQXpDSKDD73RFxWNKnSF2tGqCkIB8xrEoNlj5T9wwh2g_xrBtr_KEXnpKbyE9fvYtWaoG64JYgDe8ShiQxF4bU2q9Wv77f_g_C-Kq_2gb1g"

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