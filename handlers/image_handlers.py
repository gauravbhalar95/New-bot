import os
import tempfile
import aiofiles
import asyncio
import aiohttp
import shutil
import instaloader
import re
import traceback
from asyncio import Lock

from utils.logger import logger
from utils.sanitize import sanitize_filename
from config import DOWNLOAD_DIR, INSTAGRAM_PASSWORD, INSTAGRAM_FILE

# Instagram credentials
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "top_deals_station")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", INSTAGRAM_PASSWORD)

# Lock for safe session handling
SESSION_LOCK = Lock()

# Initialize Instaloader
INSTALOADER_INSTANCE = instaloader.Instaloader(
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    save_metadata=False,
    download_comments=False,
    post_metadata_txt_pattern=""
)


def initialize_instagram_session(force_login: bool = False):
    """Initialize or refresh Instagram session."""
    global INSTALOADER_INSTANCE
    try:
        if not force_login and os.path.exists(INSTAGRAM_FILE):
            logger.info("🔄 Trying to load saved Instagram session...")
            INSTALOADER_INSTANCE.load_session_from_file(INSTAGRAM_USERNAME, INSTAGRAM_FILE)
            if INSTALOADER_INSTANCE.context.username:
                logger.info("✅ Loaded saved session successfully.")
                return

        logger.info("🔑 Logging in with credentials (forced login)...")
        INSTALOADER_INSTANCE.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        INSTALOADER_INSTANCE.save_session_to_file(INSTAGRAM_FILE)
        logger.info("✅ Logged in and session saved.")
    except Exception as e:
        logger.error(f"❌ Instagram login failed: {e}")
        if os.path.exists(INSTAGRAM_FILE):
            os.remove(INSTAGRAM_FILE)


async def get_instaloader(force_login: bool = False):
    """Thread-safe access to instaloader instance."""
    async with SESSION_LOCK:
        if force_login or INSTALOADER_INSTANCE.context.username is None:
            initialize_instagram_session(force_login=True)
        return INSTALOADER_INSTANCE


async def get_post(shortcode):
    """Fetch Instagram post details with retry."""
    try:
        await asyncio.sleep(2)
        return await asyncio.to_thread(
            instaloader.Post.from_shortcode,
            INSTALOADER_INSTANCE.context,
            shortcode,
        )
    except Exception as e:
        if "Unauthorized" in str(e) or "Please wait" in str(e):
            logger.warning("⚠️ Session expired or rate-limited. Re-logging in...")
            await get_instaloader(force_login=True)
            await asyncio.sleep(5)
            return await asyncio.to_thread(
                instaloader.Post.from_shortcode,
                INSTALOADER_INSTANCE.context,
                shortcode,
            )
        logger.error(f"❌ Failed to fetch post {shortcode}: {e}\n{traceback.format_exc()}")
        raise


async def download_image(session, url, temp_path, final_path):
    """Download and save image."""
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(await response.read())

        await asyncio.to_thread(shutil.copy, temp_path, final_path)
        logger.info(f"✅ Downloaded: {final_path}")
        return final_path
    except Exception as e:
        logger.error(f"❌ Error downloading {url}: {e}\n{traceback.format_exc()}")
        return None


async def cleanup_temp_dir(temp_dir):
    """Cleanup temporary directory safely."""
    try:
        await asyncio.to_thread(shutil.rmtree, temp_dir, True)
    except Exception as e:
        logger.error(f"⚠️ Temp dir cleanup failed {temp_dir}: {e}")


async def process_instagram_image(url):
    """
    Process Instagram post URL and return ALL image paths + uploader.
    Handles single image, carousel (bulk), and stories.
    """
    if not url.startswith("https://www.instagram.com/"):
        logger.warning(f"⚠️ Invalid Instagram URL: {url}")
        return [], None

    image_paths, uploader_username = [], None
    temp_dir = tempfile.mkdtemp()

    async with aiohttp.ClientSession() as session:
        try:
            # --- Handle posts (single or carousel) ---
            if "/p/" in url:
                shortcode = url.split("/p/")[1].split("/")[0]
                post = await get_post(shortcode)
                uploader_username = post.owner_username

                nodes = []
                if post.typename == "GraphSidecar":
                    nodes = list(post.get_sidecar_nodes())
                else:
                    nodes = [post]

                tasks = []
                for idx, node in enumerate(nodes):
                    if node.is_video:
                        logger.info(f"⏩ Skipping video node {idx}.")
                        continue

                    filename = sanitize_filename(f"{uploader_username}_{shortcode}_{idx}.jpg")
                    final_path = os.path.join(DOWNLOAD_DIR, filename)
                    temp_path = os.path.join(temp_dir, filename)

                    if os.path.exists(final_path):
                        logger.info(f"ℹ️ Already exists: {final_path}")
                        image_paths.append(final_path)
                        continue

                    tasks.append(download_image(session, node.display_url, temp_path, final_path))

                results = await asyncio.gather(*tasks, return_exceptions=True)
                image_paths.extend([r for r in results if isinstance(r, str)])

            else:
                logger.warning("⚠️ Unsupported Instagram URL format.")
                return [], None

            return image_paths, uploader_username

        except Exception as e:
            logger.error(f"❌ Error processing Instagram image: {e}\n{traceback.format_exc()}")
            return [], None

        finally:
            asyncio.create_task(cleanup_temp_dir(temp_dir))


async def process_bulk_instagram_images(urls: list[str]):
    """
    Bulk process multiple Instagram post URLs at once.
    """
    all_downloads = []
    for url in urls:
        imgs, user = await process_instagram_image(url)
        if imgs:
            all_downloads.extend(imgs)
    return all_downloads


# Initialize session immediately
initialize_instagram_session()