import os
import logging
import yt_dlp
import instaloader
from config import DOWNLOAD_DIR, COOKIES_FILE, INSTAGRAM_USERNAME
from utils.sanitize import sanitize_filename

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure the download directory exists
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Instaloader setup (for private posts & images)
L = instaloader.Instaloader()

# Load session from file (Handles session corruption)
if os.path.exists(COOKIES_FILE):
    try:
        L.load_session_from_file(INSTAGRAM_USERNAME, COOKIES_FILE)
        logger.info("✅ Instagram session loaded successfully.")
    except Exception as e:
        logger.error(f"❌ Error loading Instagram session: {e}")
        os.remove(COOKIES_FILE)  # Remove the corrupted session file
        logger.info("⚠️ Corrupt session file removed. Please log in again.")

def process_instagram(url):
    """
    Downloads Instagram videos (yt-dlp) or images (Instaloader).
    Falls back to Instaloader for private posts.
    """
    try:
        # ✅ Use yt-dlp for videos
        ydl_opts = {
            "format": "best",
            "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
            "retries": 5,
            "socket_timeout": 10,
            "noplaylist": True,
            "cookiefile": COOKIES_FILE,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = sanitize_filename(info_dict.get("title", "instagram_post"))
            file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.{info_dict.get('ext', 'mp4')}")
            file_size = info_dict.get("filesize", 0)

            logger.info(f"✅ Video downloaded: {file_path} ({file_size} bytes)")
            return file_path, file_size

    except Exception as e:
        logger.warning(f"⚠️ yt-dlp failed, trying Instaloader... ({e})")

        # ✅ Use Instaloader for images
        try:
            shortcode = url.rstrip("/").split("/")[-1]
            post = instaloader.Post.from_shortcode(L.context, shortcode)

            user_folder = os.path.join(DOWNLOAD_DIR, post.owner_username)
            if not os.path.exists(user_folder):
                os.makedirs(user_folder)

            L.download_post(post, target=user_folder)
            logger.info(f"✅ Image downloaded: {post.url}")

            return os.path.join(user_folder, post.shortcode), 0  # No file size info from Instaloader

        except Exception as e:
            logger.error(f"❌ Error downloading with Instaloader: {e}")
            return None, 0

def download_instagram_story(username):
    """
    Downloads Instagram stories for a given username using Instaloader.
    """
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        user_id = profile.userid  # ✅ Get user ID

        story_path = os.path.join(DOWNLOAD_DIR, "stories", username)
        if not os.path.exists(story_path):
            os.makedirs(story_path)

        L.download_stories(userids=[user_id], filename_target=story_path)
        logger.info(f"✅ Stories downloaded for {username}")

        return story_path
    except Exception as e:
        logger.error(f"❌ Error downloading stories: {e}")
        return None