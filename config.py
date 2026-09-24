import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Make the bundled imageio-ffmpeg binary available to yt-dlp and subprocess calls.
try:
    import imageio_ffmpeg

    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    FFMPEG_DIR = str(Path(FFMPEG_PATH).parent)
    os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
except Exception:
    # Docker deployments may provide a system ffmpeg binary instead.
    FFMPEG_PATH = "ffmpeg"

API_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "8080"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

if not API_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL environment variable is required")
if not WEBHOOK_SECRET:
    raise RuntimeError("WEBHOOK_SECRET environment variable is required")

ADMIN_IDS = [1302277958]
DEFAULT_ADMIN = ADMIN_IDS[0]

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")
MEGA_EMAIL = os.getenv("MEGA_EMAIL", "")
MEGA_PASSWORD = os.getenv("MEGA_PASSWORD", "")

DOWNLOAD_DIR = str(BASE_DIR / "downloads")
TEMP_DIR = str(BASE_DIR / "TEMP_DIR")
DOWNLOAD_DIR3 = str(BASE_DIR / "downloads" / "story")
for directory in (DOWNLOAD_DIR, TEMP_DIR, DOWNLOAD_DIR3):
    os.makedirs(directory, exist_ok=True)

X_FILE = str(BASE_DIR / "x.txt")
YOUTUBE_FILE = str(BASE_DIR / "youtube_cookies.txt")
INSTAGRAM_FILE = str(BASE_DIR / "cookies" / "instagram_cookies.txt")
COOKIES_FILE = INSTAGRAM_FILE
FACEBOOK_FILE = str(BASE_DIR / "facebook.txt")

SUPPORTED_DOMAINS = [
    "youtube.com", "youtu.be", "facebook.com", "instagram.com",
    "x.com", "twitter.com", "xvideos.com", "xnxx.com",
    "xhamster.com", "pornhub.com",
]

MAX_CONCURRENT_DOWNLOADS = 2
CHUNK_SIZE = 8 * 1024 * 1024
MAX_RETRIES = 4
MAX_WORKERS = 3
TELEGRAM_FILE_LIMIT = 2 * 1024 * 1024 * 1024
MAX_FILE_SIZE_MB = TELEGRAM_FILE_LIMIT
