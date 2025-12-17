import os
import tempfile
import aiofiles
import asyncio
import aiohttp
import shutil
import instaloader
import traceback
import random
import time
from asyncio import Lock
from instaloader.exceptions import ConnectionException

from utils.logger import logger
from utils.sanitize import sanitize_filename
from config import DOWNLOAD_DIR

# Path to your cookie file
COOKIE_FILE = "cookies/instagram_cookies.txt"

# Lock for safe access (VERY IMPORTANT)
SESSION_LOCK = Lock()

# Instaloader configuration
INSTALOADER_INSTANCE = instaloader.Instaloader(
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    save_metadata=False,
    download_comments=False,
    post_metadata_txt_pattern="",
    quiet=True
)


# -------------------------------
# SESSION INITIALIZATION
# -------------------------------
def initialize_instagram_session():
    """Load Instagram cookies safely."""
    try:
        if os.path.exists(COOKIE_FILE):
            INSTALOADER_INSTANCE.context.load_cookies(COOKIE_FILE)
            logger.info("✅ Instagram cookies loaded successfully!")
        else:
            logger.error(f"❌ Cookie file missing: {COOKIE_FILE}")
    except Exception as e:
        logger.error(f"❌ Failed to load Instagram cookies: {e}")


# -------------------------------
# SAFE POST FETCH WITH RETRY
# -------------------------------
async def get_post(shortcode: str, retry: bool = True):
    """Fetch Instagram post with rate-limit handling."""
    async with SESSION_LOCK:
        try:
            # Mandatory random delay (Instagram protection)
            await asyncio.sleep(random.uniform(6, 10))

            return await asyncio.to_thread(
                instaloader.Post.from_shortcode,
                INSTALOADER_INSTANCE.context,
                shortcode,
            )

        except ConnectionException as e:
            error_msg = str(e)

            if "Please wait a few minutes" in error_msg and retry:
                logger.warning("⏳ Instagram rate-limited. Cooling down for 5 minutes...")
                await asyncio.sleep(300)  # 5 minutes cooldown
                return await get_post(shortcode, retry=False)

            logger.error(f"❌ Instagram blocked request: {error_msg}")
            raise

        except Exception as e:
            logger.error(
                f"❌ Error fetching post {shortcode}: {e}\n{traceback.format_exc()}"
            )
            raise


# -------------------------------
# IMAGE DOWNLOAD
# -------------------------------
async def download_image(session, url, temp_path, final_path):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
            response.raise_for_status()
            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(await response.read())

        await asyncio.to_thread(shutil.move, temp_path, final_path)
        logger.info(f"✅ Saved image: {final_path}")
        return final_path

    except Exception as e:
        logger.error(f"❌ Failed downloading image: {e}")
        return None


async def cleanup_temp_dir(temp_dir):
    try:
        await asyncio.to_thread(shutil.rmtree, temp_dir, ignore_errors=True)
    except Exception as e:
        logger.warning(f"⚠️ Temp cleanup failed {temp_dir}: {e}")


# -------------------------------
# MAIN IMAGE PROCESSOR
# -------------------------------
async def process_instagram_image(url: str):
    """Download all images from an Instagram post."""
    if "/p/" not in url:
        logger.warning("⚠️ Invalid Instagram post URL")
        return [], None

    shortcode = url.split("/p/")[1].split("/")[0]
    temp_dir = tempfile.mkdtemp()
    image_paths = []
    uploader = None

    try:
        post = await get_post(shortcode)
        uploader = post.owner_username

        nodes = (
            list(post.get_sidecar_nodes())
            if post.typename == "GraphSidecar"
            else [post]
        )

        async with aiohttp.ClientSession() as session:
            tasks = []

            for idx, node in enumerate(nodes):
                if node.is_video:
                    continue

                filename = sanitize_filename(
                    f"{uploader}_{shortcode}_{idx}.jpg"
                )
                final_path = os.path.join(DOWNLOAD_DIR, filename)
                temp_path = os.path.join(temp_dir, filename)

                if os.path.exists(final_path):
                    image_paths.append(final_path)
                    continue

                tasks.append(
                    download_image(
                        session,
                        node.display_url,
                        temp_path,
                        final_path,
                    )
                )

            results = await asyncio.gather(*tasks)
            image_paths.extend([r for r in results if r])

        return image_paths, uploader

    except Exception as e:
        logger.error(
            f"❌ Instagram image processing failed: {e}\n{traceback.format_exc()}"
        )
        return [], None

    finally:
        asyncio.create_task(cleanup_temp_dir(temp_dir))


# -------------------------------
# BULK HANDLER (SAFE SEQUENTIAL)
# -------------------------------
async def process_bulk_instagram_images(urls: list[str]):
    all_imgs = []
    for url in urls:
        imgs, _ = await process_instagram_image(url)
        all_imgs.extend(imgs)
        await asyncio.sleep(8)  # prevent bulk rate-limit
    return all_imgs


# Load cookies immediately
initialize_instagram_session()