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
    ...
    try:
        if os.path.exists(INSTAGRAM_FILE):
            INSTALOADER_INSTANCE.load_session_from_file(INSTAGRAM_USERNAME, INSTAGRAM_FILE)
            if INSTALOADER_INSTANCE.context.is_logged_in:
                logger.info("Loaded saved session.")
                return True
        ...
    except instaloader.exceptions.BadLoginException as e:
        logger.error(f"Login failed: {e}")
        if os.path.exists(INSTAGRAM_FILE): os.remove(INSTAGRAM_FILE)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

async def get_instaloader(force_login: bool = False):
    async with SESSION_LOCK:
        if force_login or not INSTALOADER_INSTANCE.context.is_logged_in:
            initialize_instagram_session(force_login=True)
        return INSTALOADER_INSTANCE

# Download, process, and cleanup functions below remain largely unchanged but with improved docstrings and flow.