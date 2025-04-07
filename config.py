import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MAX_WORKERS = "3"

API_TOKEN = os.getenv("BOT_TOKEN")  # Get from @BotFather

DROPBOX_ACCESS_TOKEN = "sl.u.AFoiEsmUa1JeCUYTwhiOxH6WfcgYFIJThvqhkhC32PoTBBTU_P3aSuGI30kzoEk-V2uMaOyxoLne0jddEVFf9iteW4Ga64vVmdNQk13lmMothdA69NFMv4V0fBxs-LLK-Mh7WRhsTG2GPq1WGFra7d3giOC01-w824Fgus6_Cb1fxBvyP_p7CdAKHl3Rx2y-8pIJ5UXRD_yDIESVVLSmWpfC6oWeHE9UOlJC-s5ViKUT8_G3OwvuToRvu_srdiYrxtK3xQQXpa4DXsIpW2H-hR6YfwLaoXGgysaQJHuxoUmzucP_AMgWOstgBeNIgivEnWy8UQxTAmqJLQsmzOWrA_b6PP8IHKQJw0c6-ujLxl-JkXoKfGP39fp2WO64rFN7_vjvw2myF6XlWJNS8lh15dM2u-O86pIcYy-oXiX-4N6Op_Y3mIOmbbjcSZXeix8FjjH8kxM_-zzdL341B48FRwksBN6N93Abyta9PHMl_zX5jlJOdED6u21pqRd4gogd5KalEbE9Exl3-XRaKm75lx5swUq7-7a5r24mhw0ISTnNmdSgpIrDtpRN9QTrKKVq--PpsvBUryy2uQXRKNiAykRjI9YfsJ7HfBDMWtLK_IAPVY5QotTOiO7y01xAGXqb2E9CA-Jdx2uwvKRr_AkdqS-32LnD5L_jvkU0wpgMXEpq4NfhfjTfOMO2oC-831AGdt4VmqzgRCLPQhMUZm0og0ssb3Og_ccPDxtsFs3BzexiFytLrneHjgwmCOhC980z9yTRxUvJ7Qc4E2qk1veSz-LXx55u646D76wdoxXgAX91uilxawOxR-znycPJcZG1aXGvlMwbYWrgIHMl7Ooi23Td7dG6iJxO0DJhwIlRmwkcRUeGI3WpO8gohi-e6kZxTay33t8eZukMpJRO6T8tP374e0LkzMQRYHDQPQfl1yIYwxsg-IqUPzJXLMtIIy1wXBy8qOP_EP2EdmStpHs-PBwYN5gaeA16p_JAcMvXy4VD_hYiDbBPv-M2nry3rlbezPBNTL5EvwWSBs6eQesKIm2GQdlOKw38ayTy65hS9M61tngDa1EUWl64oxusvCZV0kc5Mk5t2jQoDGnKK5n_Ntp7fUVVOMKQG7_msxUNHgyjXQSYs7HYc4L1c2rbKaVltmA8d7f18JziB779BWqfFeO0oatPmpAmP5GZbGmT55XB5phmWw-3Z6oR0SsN5t_2KfkdzAgQM39yBzaNvG3KqmUh3cYmW309ZJYX39HxnrWnt6OfGI7DsOVc0KgU_gsgfYDvu0LrcP6Q_h5RpWLHXRVF5XhsyPDctuMh8gDVkCW-Uw"

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