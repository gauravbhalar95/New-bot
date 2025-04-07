import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MAX_WORKERS = "3"

API_TOKEN = os.getenv("BOT_TOKEN")  # Get from @BotFather

DROPBOX_ACCESS_TOKEN = "sl.u.AFoS0qQ9doFOPaP6c38w615gVqDsEQzFGJbS4ByW_QqQnWoPs6SgSGLy6RVe3U4jznnpX2lEiZWvE6v7a6uIPHBE5lqOr_kd6uMekBVG8vq9IIreC5iDtRHOrWlIjWcqykXHe_n91yqfTzoUexO2am5tZCk1jiuWaEobVUeQCX-sN1xCZmsTpb3Lck33JdF1NdmmRP9L5vDk2QsjALB0Lxq_rQX7gqp793YoXqk5m5fmaCAVj9vhCT2w6PVPwOSqK1maTBumxqIvjIDXVXXRh5oDjb265EGcwproj7L6VRJlWY4Ziwzm8Haslm94aMJ4-qpAzU8ts4Ka6WaE05-I6_Tw0UrXkalLWDj1VyaeLDzDW7kC5BDzik1WnSY3kWk3kW8yri7j6gSuZUqjAYl4IANqb0w74ubpBsP5u0q7iTQ3AfpN7NZG9fBeJnIYpJvX8PcO93vDaHHt1WDIa4uSAYm-ZPHlvnUR0ho8K838v0HQ9GF-9KBWYFNOECkD7-WCTnw0VQYkaxgYiUvdsx7Fb_XTHpAoEOf4aUwXJsvA9cV6HGo3Yq8DKBL_xwB-n2pYeb7P_kjE8Wg1mp622MdMk5QK2mrEXi_4bK02NTI6ieDj_rYU3ZdCr8pz3ors-FLYL0vZIiydu3GbLZSenmcVBv1F2Nv50sQBJ4O02auPjiS0nq2KuGNHxacM9mVUZ5o6p2uuQ7TQoD5hnKZNzwTvd5PhMMygZFKPdYsntop6ha7d1DQoU8QADgFb_SlALFociDNu10mujxF4q7yN5v27VxxRpQdAezHD7lzN6BJY8Jlu3xrdZa-2s7O-tIvjAATe2vVuo9xMobsw8RDkC1h0mQpAbmojSFQ5hImNqReCrfxLQgS8YAz_4QO7OGn3dHgLGbRT1XGN9Np1OotHTfGUTt2tGnz6ueaaf1IwJ0eLpgsnVYf8B9DTigyak0xnJ4xlU7Zwnxivp3HYryUh823eJD-ZIHMtUbXd1OIDv7fTN2-ltmf954gWKwWYTjPy2qT8WD8I1jVD0qRMZFyTTZKgLfgrvj3Mk7l3QK8rsBtibQX_xn-z5RivY5xmTLz9v8EhGFJ0LINXJaIFiSVBdzyJUr_VXLHJDkXxlnvfBWMjOqYfmyWKOvCeCgAwppgscNrRymgiR6nP1I-7YnLnIPPQnfOzsdxge802DTCD0gc9HVzuk51KycQ8LdgtU5LwfqXcBlO0hHJ2ztcYnE0Z9tpmdl8llPjccNFc86Rz-f1RIzqT5RQqFBUuolzpNPOdPLG30DJyhMCjXTI77oXVqnbZ6plzxT5o4GVryD3z_4Xy_rMrlA"

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