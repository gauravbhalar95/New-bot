import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")  # Get from @BotFather

DROPBOX_ACCESS_TOKEN = "sl.u.AFqRl7ZAWElfGj5gCSuPrXMDXYO3SUaQ4w-Kp22DQGdHqMV49njSX-Sxq6qV5xE3o9YNwInJ9NkOSX3JbSj0OHfDxcgp3ODzj1piKP6W14TMZnwhLyrjCyZzgtOWqAADzH8QOJ3UmC090aywv-CUfO7tqFQFOGaAXkepwlEZW7ZJOwwd_o6ssi7JUviAVmqSpLbczwTqEt4FdeF4RndCMXbOWQiRQGsDGUe_L1mpIm25dnURsQGAl8JjgdA32C-RM7mLJHGH6SQvHHxBEBFpCC6vfMk2C5fv76y6K-kt4FN0GGz5sgC4UE5--Sur-Sv9PhhwLf7es_dUJYajC2GM9dfhfd8xr4ifRG1U0W52CmQ3Urz99ykmsMglm1WcNeCS52EEDZBUe-nU_X3Q9n1p2z2LosIKYBeOTwtCSPSxlEjzq3yH9tr5dQSFEhUZsLgkiHPvbCzCyu7Ht679WYS4M-0xef4Q29h6eibMxESo3ZXh64164LKJJavGR6KOvnT_9z8ttwhVeLIigawmjH1mvbmsJ3PC1PrObnhpuWxuCuT5HvzhKtV8kVPATd8sKbdOJVJGsa6v1KDP_ADWgxtQ_M0edIfgnJZo7E3smCto90j2ihTefTJWUAzSc4HqtkAnwWysQfZXiDJrFrPqJBc38pRjLcfrOBwCkO6s2gUuGD4ePwckUF74cj9L8WzBp4QrFM_xD2DyLiraw6jsFo2smPPb5sqXDn0dvTW08FpiDivNWHotavGGbJaa-Lw_Ko-_bVd3ie6iMhYocxrNWZdDNhex-9LJYXbylZXbb0ZQGWJGLKv9gYVpoyyxdoAdHVwTTFPG4IpKZQRFvrLq1wbmj8XFOTGiTflmC8hyOfX8Exd-_lOoQGMvdmDDAwK6qu-rrv99wkxyZ2npwlMMba-l2ZxpUjWIg9_iHBhRUDPagrHXRlfl9KDKcq_AOZm7y9vwQ9IxCt84F2kdnw5kuU5SSLUuchOOPOLMzAx_Hr5HRhD78XhNLF1JBtfaf8nKH3u0LF8O7HQXTAdqpTtvP5tQgAct91hsz_YTWZWiIR5LATAlOeS-bCnRIPDG7uLMwoDzraMXMYaFPwti4TZ3yF34nwFLqvpTayezfE_8ObgpgHqbnNkI06f0HuA1nZ5Sh1SVYP-g40ryCD1QWBMqPcNO2ap9TWzw2_nkYHgfXZtTDPDZlt54Mo_9VTxcwwmBB8CKAu1cGenFhqm3Z9BV5anVic7lYndjDWbplFF-Nf_8pFeR_UOW8L3Hw_DhYA1cCAlHT_6S0bnda7VGlD23QX4vl8RQfRftIz3pX_iUlhXpKJc71A"

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