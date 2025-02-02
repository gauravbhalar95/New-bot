import os
import logging
import yt_dlp
import instaloader
from instagram_private_api import Client, ClientCompatPatch
from config import DOWNLOAD_DIR, COOKIES_FILE, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD
from utils.sanitize import sanitize_filename

# Logger setup
logger = logging.getLogger(__name__)

# Instaloader instance
L = instaloader.Instaloader()

# Instagram Private API Client
api = Client(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)


def process_instagram(url):
    """
    Downloads Instagram videos, images, or stories using yt-dlp.
    Falls back to Instaloader for private content if necessary.
    """
    ydl_opts = {
        "format": "best",
        "outtmpl": f"{DOWNLOAD_DIR}/{sanitize_filename('%(title)s')}.%(ext)s",
        "retries": 5,
        "socket_timeout": 10,
        "noplaylist": True,
        "cookiefile": COOKIES_FILE,  # Use Instagram cookies
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            file_size = info_dict.get("filesize", 0)

            logger.info(f"Downloaded metadata: {info_dict}")
            logger.info(f"File saved to: {file_path}")

            return file_path, file_size

    except Exception as e:
        logger.error(f"Error downloading with yt-dlp: {e}")

        # Try using Instaloader for private posts or stories
        try:
            post = instaloader.Post.from_shortcode(L.context, url.split("/")[-2])
            L.download_post(post, target=DOWNLOAD_DIR)
            return f"{DOWNLOAD_DIR}/{post.shortcode}", 0  # No size info in Instaloader

        except Exception as e:
            logger.error(f"Error downloading with Instaloader: {e}")
            return None, 0


def get_instagram_user_info(username):
    """
    Fetches Instagram user information using the private API.
    """
    try:
        user_info = api.username_info(username)
        return {
            "full_name": user_info["user"]["full_name"],
            "followers": user_info["user"]["follower_count"],
            "following": user_info["user"]["following_count"],
            "profile_pic_url": user_info["user"]["profile_pic_url"],
        }
    except Exception as e:
        logger.error(f"Error fetching user info: {e}")
        return None


# Example Usage
if __name__ == "__main__":
    url = "https://www.instagram.com/p/XYZ123/"  # Replace with an actual post URL
    print(process_instagram(url))

    username = "instagram"
    print(get_instagram_user_info(username))