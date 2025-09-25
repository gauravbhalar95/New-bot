import os
import tempfile
import aiofiles
import asyncio
import aiohttp
import shutil
import functools
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
        await asyncio.sleep(2)  # small rate-limit delay
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


async def get_story_images(username):
    """Fetch all story image URLs for a given username."""
    try:
        await asyncio.sleep(2)
        profile = await asyncio.to_thread(
            instaloader.Profile.from_username,
            INSTALOADER_INSTANCE.context,
            username
        )
        stories = await asyncio.to_thread(
            INSTALOADER_INSTANCE.get_stories,
            [profile.userid]
        )

        return [item.url for story in stories for item in story.get_items() if not item.is_video]
    except Exception as e:
        if "Unauthorized" in str(e) or "Please wait" in str(e):
            logger.warning("⚠️ Session expired while fetching stories. Re-logging in...")
            await get_instaloader(force_login=True)
            await asyncio.sleep(5)
            return await get_story_images(username)
        logger.error(f"❌ Error fetching stories for {username}: {e}\n{traceback.format_exc()}")
        return []


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


def extract_story_username(url: str) -> str | None:
    """Extract username from story URL."""
    match = re.search(r"/stories/([^/]+)/", url)
    return match.group(1) if match else None


async def process_instagram_image(url):
    """Process Instagram post/story URL and return image paths + uploader."""
    if not url.startswith("https://www.instagram.com/"):
        logger.warning(f"⚠️ Invalid Instagram URL: {url}")
        return [], None

    image_paths, uploader_username = [], None
    temp_dir = tempfile.mkdtemp()

    async with aiohttp.ClientSession() as session:
        try:
            # Handle posts
            if "/p/" in url:
                shortcode = url.split("/p/")[1].split("/")[0]
                post = await get_post(shortcode)
                uploader_username = post.owner_username
                nodes = post.get_sidecar_nodes() if hasattr(post, "get_sidecar_nodes") else [post]

                tasks = []
                for idx, node in enumerate(nodes):
                    if node.is_video:
                        logger.info(f"⏩ Skipping video node {idx}.")
                        continue

                    filename = sanitize_filename(f"{uploader_username}_{shortcode}_{idx}.png")
                    final_path = os.path.join(DOWNLOAD_DIR, filename)
                    temp_path = os.path.join(temp_dir, filename)

                    if os.path.exists(final_path):
                        logger.info(f"ℹ️ Already exists: {final_path}")
                        image_paths.append(final_path)
                        continue

                    tasks.append(download_image(session, node.display_url, temp_path, final_path))

                results = await asyncio.gather(*tasks, return_exceptions=True)
                image_paths.extend([r for r in results if isinstance(r, str)])

            # Handle stories
            elif "/stories/" in url:
                uploader_username = extract_story_username(url)
                if not uploader_username:
                    logger.warning("⚠️ Could not extract username from story URL.")
                    return [], None

                story_urls = await get_story_images(uploader_username)
                tasks = []
                for idx, image_url in enumerate(story_urls):
                    filename = sanitize_filename(f"{uploader_username}_story_{idx}.png")
                    final_path = os.path.join(DOWNLOAD_DIR, filename)
                    temp_path = os.path.join(temp_dir, filename)

                    if os.path.exists(final_path):
                        logger.info(f"ℹ️ Already exists: {final_path}")
                        image_paths.append(final_path)
                        continue

                    tasks.append(download_image(session, image_url, temp_path, final_path))

                results = await asyncio.gather(*tasks, return_exceptions=True)
                image_paths.extend([r for r in results if isinstance(r, str)])

            else:
                logger.warning("⚠️ Unrecognized Instagram URL format.")
                return [], None

            return image_paths, uploader_username

        except Exception as e:
            logger.error(f"❌ Error processing Instagram image: {e}\n{traceback.format_exc()}")
            return [], None

        finally:
            asyncio.create_task(cleanup_temp_dir(temp_dir))  # shield cleanup
            

# Initialize session immediately
initialize_instagram_session()