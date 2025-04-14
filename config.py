import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MAX_WORKERS = "3"

API_TOKEN = os.getenv("BOT_TOKEN")  # Get from @BotFather

DROPBOX_ACCESS_TOKEN = "sl.u.AFrbmhHWHEA2auyOi2Bm1vSnyy-Rgaw3ieoeTwyIk3Qqks0XYw_RDGXfPEypna1RjB4oMkH2j2pRqLU5G8Mb2r3GtJUnLhAUqx4CtiHagh2n5M2Zio6yS_3zh_1Q_ODRAuJXTAFQoWarTsrYYI2ul4C8ceJBDbe1PCpAQMPD-vxQYzPzdjUipytODfPiF6751dz90XqZLCjwUs1417RPIvbyYhHHUe7fH90CSPfJouo0lU4wWNhcHHwv_iyxpD1bwERNwjEdQEYccgd79b471U2h9C93IrMdmzwelIgiYjQee3NkRejNdYO_Oqd1gRN_rNN_4nNkpHlB5_T3xG7EL7nL5zPOIvsrDBBk6UrUf-UXzEpPpHI3VdT_CkJeSKTDIMKyphaX2NPCvvdhqeLnmUt9YO9Gg-_iCvhzTxgOMzrI5pMI2al08_hVzAnTfyEVwy5l9idjEBT-pIdVR_ctBPYFetnjEN1DTh2QFUMAOQ9coQr2HGlQmHKnsQ7PNJ-v4fm8CnMjHCoVFDbX3C8SWsjgKcjGX00ihjX3i5Etb3YR7kPZEvTsT6PajZKwwVUTD7yfuQUll0_TNZN06ta-XJz3E9Fb1s_kH1_KOzBtJGiBtRBRyV_ojmP416YbRK3y2rpooloYjfqnuGmD0gEgRvTP4DBFACvde3cC7EcvMBr_0VRz5VHpmBvhgOSEPyQZHYqurfjUleASvmpIrq1dtHn_3FywpPEZHOAsPF8LtdFZRWDr9YU2CqGOPdYOmArKrGRGh11v0OXUUFAnDpC6rkjbiXFqJLakCXSWgzS0GpKqVYDKt1zoD0wUn6TznVU94PufQ9ncYaxjaXaxrVd3GaIh3ul__YN9SoU_8WWU3fwlKWqEieHjOA69AM2GcYdt3BaxK520Xz6EbMqcu4aqWVj3JMo03yiQThqpNdL6F7TxCnn5jjxVNoO9XAD8SxKa25R7q9u-DpI4vtTkOD6Sr9RAz4RSfhEYbIQuvqxPIqiX-nts4Gf8zaGl48O1unRUyq2lcjnjQF5pFdtphwmTrslXILTFhbBKqUCSnGR4il3VXFOe9xosua2Le8tdtFvFYexLVUrerVV4rWXqTgkK7PYrvm6x7MW6-bZULsraYSZQJM5jSV2euygF5rIZTaf_hMjv2QOti46bNZRcDcM0dU4t-9CrFnQoCRhT3x_d_0kbXPVd2wyzaycbFzFsyRd95ovnZBV6iqaa4vgHYkLIqlZBAnmUh8FPp1JvBOoQac_HAsRgsUkgyrbEHjKQ-jUmY3djlSDMtH65e6sBrVvTZQ8FVco6OncasbbMQMUP6osMIQ"

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