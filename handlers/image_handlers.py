import os
import tempfile
import aiofiles
import asyncio
import aiohttp
import shutil
import instaloader
import traceback
from asyncio import Lock

from utils.logger import logger
from utils.sanitize import sanitize_filename
from config import DOWNLOAD_DIR, INSTAGRAM_FILE

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "top_deals_station")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
SESSION_LOCK = Lock()
INSTALOADER_INSTANCE = instaloader.Instaloader(download_videos=False)

def initialize_instagram_session(force_login: bool = False):
    """
    Initializes or restores an Instaloader session. Logs in if necessary.
    """
    try:
        if os.path.exists(INSTAGRAM_FILE):
            INSTALOADER_INSTANCE.load_session_from_file(INSTAGRAM_USERNAME, INSTAGRAM_FILE)
            if INSTALOADER_INSTANCE.context.is_logged_in and not force_login:
                logger.info("Loaded saved session.")
                return True
        # Login if session file not present or force_login requested
        logger.info("Logging into Instagram...")
        INSTALOADER_INSTANCE.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        INSTALOADER_INSTANCE.save_session_to_file(INSTAGRAM_FILE)
        logger.info("Logged in and session saved.")
        return True
    except instaloader.exceptions.BadLoginException as e:
        logger.error(f"Login failed: {e}")
        if os.path.exists(INSTAGRAM_FILE):
            os.remove(INSTAGRAM_FILE)
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        traceback.print_exc()
        return False

async def get_instaloader(force_login: bool = False):
    """
    Returns a ready-to-use Instaloader instance with a valid login session.
    Uses an async lock to avoid race conditions across coroutines.
    """
    async with SESSION_LOCK:
        if force_login or not INSTALOADER_INSTANCE.context.is_logged_in:
            initialize_instagram_session(force_login=True)
        return INSTALOADER_INSTANCE

async def process_instagram_image(post_url: str, download_dir: str = DOWNLOAD_DIR):
    """
    Downloads an image from an Instagram post URL to a temporary directory.
    Returns the local file path to the downloaded image.
    """
    loader = await get_instaloader()
    shortcode = post_url.strip('/').split('/')[-1]
    tempdir = tempfile.mkdtemp(dir=download_dir)
    try:
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        for idx, res in enumerate(post.get_sidecar_nodes(), start=1):
            image_url = res.display_url
            file_ext = image_url.split("?")[0].split(".")[-1]
            filename = f"{sanitize_filename(shortcode)}_{idx}.{file_ext}"
            filepath = os.path.join(tempdir, filename)
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        f = await aiofiles.open(filepath, mode='wb')
                        await f.write(await resp.read())
                        await f.close()
            logger.info(f"Downloaded: {filepath}")
        return tempdir
    except Exception as e:
        logger.error(f"Failed to process Instagram post: {e}")
        shutil.rmtree(tempdir, ignore_errors=True)
        raise