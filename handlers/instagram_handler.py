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
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Instaloader setup (for private posts & images)
L = instaloader.Instaloader()

# Load Instagram session from cookies
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
    Downloads Instagram videos using yt-dlp or images using Instaloader.
    If the file path does not exist, it automatically retries with Instaloader.
    """
    try:
        # Ensure the download directory exists
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        # ✅ Try downloading with yt-dlp (preferred for videos)
        ydl_opts = {
            "format": "best",
            "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
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
            file_ext = info_dict.get("ext", "mp4")
            file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.{file_ext}")

            # ✅ If file exists, return it
            if os.path.exists(file_path):
                logger.info(f"✅ Video downloaded successfully: {file_path}")
                return file_path, os.path.getsize(file_path)

            logger.warning(f"⚠️ yt-dlp did not create the expected file. Retrying with Instaloader...")

    except Exception as e:
        logger.warning(f"⚠️ yt-dlp failed: {e}. Retrying with Instaloader...")

    # ✅ Use Instaloader as fallback (for images and private content)
    try:
        shortcode = url.rstrip("/").split("/")[-1]
        post = instaloader.Post.from_shortcode(L.context, shortcode)

        user_folder = os.path.join(DOWNLOAD_DIR, post.owner_username)
        os.makedirs(user_folder, exist_ok=True)

        L.download_post(post, target=user_folder)

        # ✅ Find the downloaded file
        post_files = os.listdir(user_folder)
        if post_files:
            post_path = os.path.join(user_folder, post_files[0])
            logger.info(f"✅ Post downloaded successfully: {post_path}")
            return post_path, os.path.getsize(post_path)

        logger.error("❌ Instaloader did not create any files.")
        return None, 0

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
        os.makedirs(story_path, exist_ok=True)

        L.download_stories(userids=[user_id], filename_target=story_path)
        logger.info(f"✅ Stories downloaded for {username}")

        return story_path
    except Exception as e:
        logger.error(f"❌ Error downloading stories: {e}")
        return None