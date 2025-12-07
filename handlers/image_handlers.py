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
from config import DOWNLOAD_DIR

# Path to your cookie file
COOKIE_FILE = "cookies/instagram_cookies.txt"

# Lock for safe access
SESSION_LOCK = Lock()

# Instaloader configuration
INSTALOADER_INSTANCE = instaloader.Instaloader(
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    save_metadata=False,
    download_comments=False,
    post_metadata_txt_pattern=""
)

def initialize_instagram_session():
    """Load cookies directly. No login required."""
    global INSTALOADER_INSTANCE
    try:
        if os.path.exists(COOKIE_FILE):
            INSTALOADER_INSTANCE.context.load_cookies(COOKIE_FILE)
            logger.info("✅ Instagram cookies loaded successfully!")
        else:
            logger.error("❌ Cookie file missing! Expected at: cookies/instagram_cookies.txt")
    except Exception as e:
        logger.error(f"❌ Failed to load cookies: {e}")

async def get_instaloader():
    """Thread-safe loader access."""
    async with SESSION_LOCK:
        return INSTALOADER_INSTANCE

async def get_post(shortcode):
    """Fetch Instagram post using cookies only."""
    try:
        await asyncio.sleep(1)
        return await asyncio.to_thread(
            instaloader.Post.from_shortcode,
            INSTALOADER_INSTANCE.context,
            shortcode,
        )
    except Exception as e:
        logger.error(f"❌ Error fetching post {shortcode}: {e}\n{traceback.format_exc()}")
        raise

async def download_image(session, url, temp_path, final_path):
    """Download single image."""
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(await response.read())

        await asyncio.to_thread(shutil.copy, temp_path, final_path)
        logger.info(f"✅ Saved image: {final_path}")
        return final_path

    except Exception as e:
        logger.error(f"❌ Failed downloading {url}: {e}")
        return None

async def cleanup_temp_dir(temp_dir):
    try:
        await asyncio.to_thread(shutil.rmtree, temp_dir, ignore_errors=True)
    except Exception as e:
        logger.warning(f"⚠️ Failed to cleanup temp directory {temp_dir}: {e}")

async def process_instagram_image(url):
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

        nodes = list(post.get_sidecar_nodes()) if post.typename == "GraphSidecar" else [post]
        tasks = []

        async with aiohttp.ClientSession() as session:
            for idx, node in enumerate(nodes):
                if node.is_video:
                    continue

                filename = sanitize_filename(f"{uploader}_{shortcode}_{idx}.jpg")
                final_path = os.path.join(DOWNLOAD_DIR, filename)
                temp_path = os.path.join(temp_dir, filename)

                if os.path.exists(final_path):
                    image_paths.append(final_path)
                    continue

                tasks.append(download_image(session, node.display_url, temp_path, final_path))

            results = await asyncio.gather(*tasks)
            image_paths.extend([r for r in results if r])

        return image_paths, uploader

    except Exception as e:
        logger.error(f"❌ Instagram image processing failed: {e}\n{traceback.format_exc()}")
        return [], None

    finally:
        asyncio.create_task(cleanup_temp_dir(temp_dir))


async def process_bulk_instagram_images(urls: list[str]):
    all_imgs = []
    for url in urls:
        imgs, _ = await process_instagram_image(url)
        all_imgs.extend(imgs)
    return all_imgs


# Load cookies immediately
initialize_instagram_session()