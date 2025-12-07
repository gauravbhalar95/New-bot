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
from config import DOWNLOAD_DIR, INSTAGRAM_PASSWORD as CONFIG_IG_PASSWORD, INSTAGRAM_FILE

# Instagram credentials (priority: environment → config)
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "top_deals_station")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", CONFIG_IG_PASSWORD)

# Async lock
SESSION_LOCK = Lock()

# Instaloader instance
INSTALOADER_INSTANCE = instaloader.Instaloader(
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    save_metadata=False,
    download_comments=False,
    post_metadata_txt_pattern=""
)


def initialize_instagram_session(force_login: bool = False):
    """Initialize or refresh Instaloader Instagram session."""
    global INSTALOADER_INSTANCE

    try:
        # Load saved session
        if not force_login and os.path.exists(INSTAGRAM_FILE):
            logger.info("🔄 Loading saved Instagram session...")
            INSTALOADER_INSTANCE.load_session_from_file(INSTAGRAM_USERNAME, INSTAGRAM_FILE)

            if INSTALOADER_INSTANCE.context.username:
                logger.info("✅ Session loaded successfully.")
                return

        # Force login
        logger.info("🔑 Logging into Instagram...")
        INSTALOADER_INSTANCE.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        INSTALOADER_INSTANCE.save_session_to_file(INSTAGRAM_FILE)

        logger.info("✅ Login successful & session saved.")

    except Exception as e:
        logger.error(f"❌ Instagram session initialization failed: {e}")
        if os.path.exists(INSTAGRAM_FILE):
            os.remove(INSTAGRAM_FILE)


async def get_instaloader(force_login: bool = False):
    """Thread-safe Instaloader instance access."""
    async with SESSION_LOCK:
        if force_login or INSTALOADER_INSTANCE.context.username is None:
            initialize_instagram_session(force_login=True)
        return INSTALOADER_INSTANCE


async def get_post(shortcode):
    """Fetch Instagram post details with automatic login recovery."""
    try:
        await asyncio.sleep(1)
        return await asyncio.to_thread(
            instaloader.Post.from_shortcode,
            INSTALOADER_INSTANCE.context,
            shortcode
        )

    except Exception as e:
        # Auto-login on session expiry
        if "Unauthorized" in str(e) or "Please wait" in str(e):
            logger.warning("⚠️ IG session expired. Re-logging in...")
            await get_instaloader(force_login=True)
            await asyncio.sleep(3)

            return await asyncio.to_thread(
                instaloader.Post.from_shortcode,
                INSTALOADER_INSTANCE.context,
                shortcode
            )

        logger.error(f"❌ Error fetching post {shortcode}: {e}\n{traceback.format_exc()}")
        raise


async def download_image(session, url, temp_path, final_path):
    """Download an image and save it."""
    try:
        async with session.get(url) as resp:
            resp.raise_for_status()
            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(await resp.read())

        await asyncio.to_thread(shutil.copy, temp_path, final_path)
        logger.info(f"✅ Saved image: {final_path}")

        return final_path

    except Exception as e:
        logger.error(f"❌ Image download failed: {e}\n{traceback.format_exc()}")
        return None


async def cleanup_temp_dir(temp_dir):
    """Delete temporary directory."""
    try:
        await asyncio.to_thread(shutil.rmtree, temp_dir, True)
    except Exception as e:
        logger.error(f"⚠️ Temp cleanup failed: {e}")


async def process_instagram_image(url):
    """Download images from any Instagram post (single or carousel)."""
    if "instagram.com" not in url:
        return [], None

    temp_dir = tempfile.mkdtemp()
    images_list = []
    uploader = None

    try:
        if "/p/" not in url:
            logger.warning("⚠️ Unsupported Instagram URL.")
            return [], None

        shortcode = url.split("/p/")[1].split("/")[0]
        post = await get_post(shortcode)
        uploader = post.owner_username

        # Select sidecar nodes or single
        nodes = (
            list(post.get_sidecar_nodes())
            if post.typename == "GraphSidecar"
            else [post]
        )

        async with aiohttp.ClientSession() as session:
            download_tasks = []

            for index, node in enumerate(nodes):
                if node.is_video:
                    continue  # skip videos

                filename = sanitize_filename(f"{uploader}_{shortcode}_{index}.jpg")
                final_path = os.path.join(DOWNLOAD_DIR, filename)
                temp_path = os.path.join(temp_dir, filename)

                # Skip existing
                if os.path.exists(final_path):
                    images_list.append(final_path)
                    continue

                download_tasks.append(
                    download_image(session, node.display_url, temp_path, final_path)
                )

            results = await asyncio.gather(download_tasks, return_exceptions=True)
            images_list.extend([p for p in results if isinstance(p, str)])

        return images_list, uploader

    except Exception as e:
        logger.error(f"❌ process_instagram_image: {e}\n{traceback.format_exc()}")
        return [], None

    finally:
        asyncio.create_task(cleanup_temp_dir(temp_dir))


async def process_bulk_instagram_images(urls: list[str]):
    """Download images from multiple post URLs."""
    all_imgs = []
    for u in urls:
        imgs, _ = await process_instagram_image(u)
        all_imgs.extend(imgs)
    return all_imgs


# Initialize session on import
initialize_instagram_session()