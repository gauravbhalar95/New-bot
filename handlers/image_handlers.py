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
from config import DOWNLOAD_DIR, INSTAGRAM_PASSWORD

# Instagram credentials
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "top_deals_station")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", INSTAGRAM_PASSWORD)
COOKIE_FILE = "Lcookies.txt"

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


def initialize_instagram_session():
    """Always login with credentials, overwrite old session."""
    global INSTALOADER_INSTANCE
    logger.info("🔑 Forcing Instagram login with credentials...")

    try:
        INSTALOADER_INSTANCE.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        INSTALOADER_INSTANCE.save_session_to_file(COOKIE_FILE)
        logger.info("✅ Logged in and session saved (forced login).")
    except Exception as e:
        logger.error(f"❌ Instagram forced login failed: {e}")
        # Remove cookies if login failed
        if os.path.exists(COOKIE_FILE):
            os.remove(COOKIE_FILE)


async def get_instaloader(force_login: bool = False):
    """Thread-safe wrapper for accessing instaloader instance with forced login if needed."""
    async with SESSION_LOCK:
        if force_login or INSTALOADER_INSTANCE.context.username is None:
            initialize_instagram_session()
        return INSTALOADER_INSTANCE


async def get_post(shortcode):
    """Fetch Instagram post details from shortcode with retry on failure."""
    loop = asyncio.get_event_loop()
    try:
        await asyncio.sleep(2)  # rate-limit delay
        return await loop.run_in_executor(
            None,
            functools.partial(
                instaloader.Post.from_shortcode,
                INSTALOADER_INSTANCE.context,
                shortcode,
            ),
        )
    except Exception as e:
        if "Unauthorized" in str(e) or "Please wait" in str(e):
            logger.warning("⚠️ Session expired or rate-limited. Forcing re-login...")
            await get_instaloader(force_login=True)
            await asyncio.sleep(5)
            return await loop.run_in_executor(
                None,
                functools.partial(
                    instaloader.Post.from_shortcode,
                    INSTALOADER_INSTANCE.context,
                    shortcode,
                ),
            )
        logger.error(f"❌ Failed to fetch post {shortcode}: {e}\n{traceback.format_exc()}")
        raise


async def get_story_images(username):
    """Fetch story images for a given username."""
    try:
        loop = asyncio.get_event_loop()
        await asyncio.sleep(2)
        profile = await loop.run_in_executor(
            None, lambda: instaloader.Profile.from_username(INSTALOADER_INSTANCE.context, username)
        )
        stories = await loop.run_in_executor(
            None, lambda: INSTALOADER_INSTANCE.get_stories(userids=[profile.userid])
        )

        image_urls = []
        for story in stories:
            for item in story.get_items():
                if not item.is_video:
                    image_urls.append(item.url)

        return image_urls
    except Exception as e:
        if "Unauthorized" in str(e) or "Please wait" in str(e):
            logger.warning("⚠️ Session expired while fetching stories. Forcing re-login...")
            await get_instaloader(force_login=True)
            await asyncio.sleep(5)
            return await get_story_images(username)
        logger.error(f"❌ Error fetching stories for {username}: {e}\n{traceback.format_exc()}")
        return []


async def download_image(session, url, temp_path, permanent_path):
    """Download and save image to final path."""
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(await response.read())

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, shutil.copy, temp_path, permanent_path)
        logger.info(f"✅ Downloaded image to {permanent_path}")
        return permanent_path
    except Exception as e:
        logger.error(f"❌ Error downloading image {url}: {e}\n{traceback.format_exc()}")
        return None


async def cleanup_temp_dir(temp_dir):
    """Remove temporary directory safely."""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            functools.partial(shutil.rmtree, temp_dir, ignore_errors=True)
        )
    except Exception as cleanup_error:
        logger.error(f"⚠️ Error cleaning up temp directory {temp_dir}: {cleanup_error}")


def extract_story_username(url: str) -> str | None:
    """Extract username from story URL reliably."""
    match = re.search(r"/stories/([^/]+)/", url)
    return match.group(1) if match else None


async def process_instagram_image(url):
    """Process Instagram post/story URL and return downloaded image paths + uploader username."""
    if not url.startswith("https://www.instagram.com/"):
        logger.warning(f"⚠️ Invalid Instagram URL: {url}")
        return [], None

    image_paths = []
    uploader_username = None
    temp_dir = tempfile.mkdtemp()

    async with aiohttp.ClientSession() as session:
        try:
            # Handle Instagram Posts
            if "/p/" in url:
                shortcode = url.split("/p/")[1].split("/")[0]
                try:
                    post = await get_post(shortcode)
                except Exception:
                    logger.warning("⚠️ Post fetch failed. Forcing re-login...")
                    await get_instaloader(force_login=True)
                    post = await get_post(shortcode)

                uploader_username = post.owner_username
                nodes = post.get_sidecar_nodes() if hasattr(post, "get_sidecar_nodes") else [post]

                tasks = []
                for idx, node in enumerate(nodes):
                    if not node.is_video:
                        image_url = node.display_url
                        filename = sanitize_filename(f"{uploader_username}_{shortcode}_{idx}.png")
                        temp_path = os.path.join(temp_dir, filename)
                        final_path = os.path.join(DOWNLOAD_DIR, filename)

                        if os.path.exists(final_path):
                            logger.info(f"ℹ️ File already exists: {final_path}")
                            image_paths.append(final_path)
                            continue

                        tasks.append(download_image(session, image_url, temp_path, final_path))
                    else:
                        logger.info(f"⏩ Skipping video node {idx}.")

                results = await asyncio.gather(*tasks)
                image_paths.extend([res for res in results if res])

            # Handle Instagram Stories
            elif "/stories/" in url:
                uploader_username = extract_story_username(url)
                if not uploader_username:
                    logger.warning("⚠️ Could not extract username from story URL.")
                    return [], None

                story_image_urls = await get_story_images(uploader_username)

                tasks = []
                for idx, image_url in enumerate(story_image_urls):
                    filename = sanitize_filename(f"{uploader_username}_story_{idx}.png")
                    temp_path = os.path.join(temp_dir, filename)
                    final_path = os.path.join(DOWNLOAD_DIR, filename)

                    if os.path.exists(final_path):
                        logger.info(f"ℹ️ File already exists: {final_path}")
                        image_paths.append(final_path)
                        continue

                    tasks.append(download_image(session, image_url, temp_path, final_path))

                results = await asyncio.gather(*tasks)
                image_paths.extend([res for res in results if res])

            else:
                logger.warning("⚠️ Unrecognized Instagram URL format.")
                return [], None

            return image_paths, uploader_username

        except Exception as e:
            logger.error(f"❌ Error processing Instagram image: {e}\n{traceback.format_exc()}")
            return [], None

        finally:
            await cleanup_temp_dir(temp_dir)


# Force login immediately on module load
initialize_instagram_session()