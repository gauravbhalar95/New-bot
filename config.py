import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add this to config.py
ADMIN_IDS = [
    1302277958,  # Your Telegram ID
]
DEFAULT_ADMIN = 1302277958  # Your Telegram ID as the default admin

WEBHOOK_PORT = 8443  # Changed from PORT to be more specific
HEALTH_CHECK_PORT = 8080  # New configuration for health check port





# Base directory of the project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# SSL Certificate paths
SSL_CERT = os.path.join(BASE_DIR, 'certs', 'cert.pem')
SSL_PRIV = os.path.join(BASE_DIR, 'certs', 'private.key')



# In config.py
MAX_CONCURRENT_DOWNLOADS = 2

# Size of chunks for streaming operations (8MB)
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB in bytes

MAX_RETRIES = "4"

MAX_WORKERS = "3"

API_TOKEN = os.getenv("BOT_TOKEN")  # Get from @BotFather
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = os.getenv("PORT")

INSTAGRAM_PASSWORD = "GAURAV74$"
INSTAGRAM_USERNAME = "top_deals_station"

MEGA_EMAIL = os.getenv("MEGA_EMAIL")
MEGA_PASSWORD = os.getenv("MEGA_PASSWORD")


DROPBOX_ACCESS_TOKEN = "sl.u.AFrF8q0y928QgOnmGr5uko5it431FfQgVEhmXyB-ZMy-MUTsNzoasBGXvJEcQ7A293krlGwWNqzwEAHFW9IWACNiI_oEeHmszZMm2OTV4_VlYtqXZkN4jAGy8voMHdxKsn0jqYhkSDz2EbI0hLaHDX_Q9NuXPH8rkbDMkk-2gd0dZ1MkIVFC3uHaaa4YTQC0yfeEzbi1LajYyFj1d08hJOe3W1Nhjv1AB21FRNMNOMznRpFvxW6qxGk-hVe-iAeaS_cOhveXZUh7jQijr9vUq-tXxZQKgwM782Q4WzBuvP2EaoOGqQt4CUHFh2CWNkTUzg85-zFOKqRsEUkstrOcgYK2WiigE-z1KJnCis85Op76CjC6YtyruPxyCFPVQ0Y1eZzZzYA1r62GuAQq05_tfRKtREh14Ja3QucpugW469F3ye5-ZkyrHXgDzH1Os6VEPpyvVjcHMtaSLjIjboOJXl_ZlNhQJoX0atJ8R7NrWKz1d_l2yxhQD4FJxw--iZaDBgHF-Ur4nYwYen2CiOFiGWRkxTA1Q4DWVARNZXPfTeNMhqtY8LSOrRSbE4RKJdogag-ZG5mJXgsFXRNq5-4e4_zRYhgszo194qYE5wOuYzWHTtDXZsHxTI_XCop0EYUxpPCucN3XmzxiOTXwLLNtI2x-sQtCvbDxobksFuHF5tyS_VQC0NQUqSdTKNPCCKp0Q5LgdjjWZnM0BN6JBzmm7Q6iLpm8OJlfwGNPaJ3i-ROSZkSwjMZ6y-IkfhngDg6_S1bzFjRSe03g9ot8GWYJ4mQMqAHSB8s2tXRhKIqFb6gZdtFFgZI9nWCfi3J5qnPQLqKGlnCANS4Z-tgUqjLM8S4ET21riFMtFwPGa1GloqGj5l2nNmZaw5aVU-GCGVbkkQ_QV_-1RAs1tyUYeH8slUk2jCRHykD8RkWFlWNfcO2zeyHf8MhxIWyAutdenD8QSmrAoAKAJS1_JEoQiAY1SdaX7NcDUD8_gByOw-gLZbrRn_fubF8MQAN6gq9BVRtbssB77uyvXMdGlD8aoqj7MxxvQ_zmEdR4lnNzfKbCWSdUcyD5-aiCyHwHl8co3nC1KNlGIUii38UYcX6-wJq3Nr6704D8opLBsawa6YUDpuMJOeotheGfrMZ9iWKIEn40arwavlNUyNigkG4usSU9jgOCxEW1xFKocrtKlTvqM3gje6UqnWYd2GdRlNcT4E6Vo3cilWSPpJ36D4cQELf4I47Fx1yWpqF7r8yXrPninZZSOv8KZrNPfGcrE602i-Php-Z2N_TF_FjXHi-n0blXSmgpUThv9R2woM6WdrNx0IqR6A"
DROPBOX_APP_SECRET = "i34g2leylb8txhv"
DROPBOX_APP_KEY = "1k435aevlnbnngz"
DROPBOX_REFRESH_TOKEN = "bHxlbNdZW6YAAAAAAAAAYHFqUuBlvtDt0DIjem4RVQE"

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