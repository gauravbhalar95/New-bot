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

# Official Instagram Business Login / Instagram API with Instagram Login.
# These values must be configured as deployment secrets, never committed.
INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID", "").strip()
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET", "").strip()
INSTAGRAM_OAUTH_SCOPES = os.getenv(
    "INSTAGRAM_OAUTH_SCOPES",
    "instagram_business_basic",
).strip()
INSTAGRAM_REDIRECT_URI = os.getenv(
    "INSTAGRAM_REDIRECT_URI",
    f"{WEBHOOK_URL.rsplit('/', 1)[0]}/instagram/callback" if "/" in WEBHOOK_URL else "",
).strip()
MINIAPP_URL = os.getenv(
    "MINIAPP_URL",
    f"{WEBHOOK_URL.rsplit('/', 1)[0]}/miniapp" if "/" in WEBHOOK_URL else "",
).strip()

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
INSTAGRAM_SESSIONID = os.getenv("INSTAGRAM_SESSIONID", "").strip()
# Optional CSRF cookie from the same authenticated Instagram session.
INSTAGRAM_CSRFTOKEN = os.getenv("INSTAGRAM_CSRFTOKEN", "").strip()
# Automatic Instagram session maintenance. The default refresh interval is
# deliberately conservative to reduce unnecessary login/challenge requests.
INSTAGRAM_AUTO_LOGIN = os.getenv("INSTAGRAM_AUTO_LOGIN", "false").strip().lower() not in {
    "0", "false", "no", "off"
}
try:
    INSTAGRAM_COOKIE_REFRESH_HOURS = max(
        1,
        int(os.getenv("INSTAGRAM_COOKIE_REFRESH_HOURS", "168"))
    )
except ValueError:
    INSTAGRAM_COOKIE_REFRESH_HOURS = 168
MEGA_EMAIL = os.getenv("MEGA_EMAIL", "")
MEGA_PASSWORD = os.getenv("MEGA_PASSWORD", "")

DOWNLOAD_DIR = str(BASE_DIR / "downloads")
TEMP_DIR = str(BASE_DIR / "TEMP_DIR")
DOWNLOAD_DIR3 = str(BASE_DIR / "downloads" / "story")
for directory in (DOWNLOAD_DIR, TEMP_DIR, DOWNLOAD_DIR3):
    os.makedirs(directory, exist_ok=True)

X_FILE = str(BASE_DIR / "x.txt")
# YouTube uses its own separate Netscape-format cookie file.
# Provide youtube_cookies.txt at the project root (/app/youtube_cookies.txt)
# through the deployment file/secret mechanism; do not use Instagram cookies.
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
