import os
import tempfile
import aiofiles
import asyncio
import aiohttp
import shutil
import functools
import instaloader
from PIL import Image
import re
from utils.logger import logger
from utils.sanitize import sanitize_filename
from config import DOWNLOAD_DIR, INSTAGRAM_PASSWORD

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 2
RATE_LIMIT_DELAY = 1

# Initialize Instaloader instance with optimized settings
INSTALOADER_INSTANCE = instaloader.Instaloader(
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    save_metadata=False,
    download_comments=False,
    post_metadata_txt_pattern='',
    quiet=True,
    compress_json=False,
    fatal_status_codes=[429, 401, 403]  # Handle rate limiting and authentication errors
)

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "top_deals_station")

async def retry_with_backoff(func, *args, max_retries=MAX_RETRIES, **kwargs):
    """Generic retry function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = RETRY_DELAY ** attempt
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay} seconds...")
            await asyncio.sleep(delay)

def initialize_instagram_session():
    """Initialize Instagram session with proper authentication."""
    logger.info("Initializing Instagram session...")
    try:
        if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
            raise ValueError("Instagram credentials not properly configured")

        if os.path.exists("instagram_cookies.txt"):
            try:
                INSTALOADER_INSTANCE.load_session_from_file(INSTAGRAM_USERNAME, "instagram_cookies.txt")
                logger.info("Instagram session loaded successfully from cookies")
                return
            except Exception as e:
                logger.warning(f"Failed to load session from cookies: {e}")

        # Attempt direct login
        logger.info("Attempting direct login...")
        INSTALOADER_INSTANCE.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        INSTALOADER_INSTANCE.save_session_to_file("instagram_cookies.txt")
        logger.info("Successfully logged in and saved session")

    except Exception as e:
        logger.error(f"Failed to initialize Instagram session: {e}")
        raise

async def get_post(shortcode):
    """Fetch Instagram post with retry logic."""
    logger.info(f"Fetching post with shortcode: {shortcode}")
    async def _fetch():
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            functools.partial(instaloader.Post.from_shortcode, INSTALOADER_INSTANCE.context, shortcode)
        )
    return await retry_with_backoff(_fetch)

async def get_story_images(username):
    """Fetch story images with retry logic."""
    logger.info(f"Fetching stories for user: {username}")
    try:
        loop = asyncio.get_event_loop()
        profile = await loop.run_in_executor(
            None,
            lambda: instaloader.Profile.from_username(INSTALOADER_INSTANCE.context, username)
        )
        
        stories = await loop.run_in_executor(
            None,
            lambda: INSTALOADER_INSTANCE.get_stories(userids=[profile.userid])
        )

        image_urls = []
        for story in stories:
            for item in story.get_items():
                if not item.is_video:
                    image_urls.append(item.url)

        logger.info(f"Found {len(image_urls)} story images")
        return image_urls

    except Exception as e:
        logger.error(f"Error fetching stories for {username}: {e}")
        return []

async def download_image(session, url, temp_path, permanent_path):
    """Download image with retry logic and validation."""
    async def _download():
        async with session.get(url) as response:
            response.raise_for_status()
            content = await response.read()
            
            # Validate image data
            if not content.startswith(b'\xff\xd8') and not content.startswith(b'\x89PNG'):
                raise ValueError("Invalid image data received")

            async with aiofiles.open(temp_path, 'wb') as f:
                await f.write(content)

            # Validate image with PIL
            try:
                Image.open(temp_path).verify()
            except Exception:
                raise ValueError("Failed to verify image integrity")

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.copy, temp_path, permanent_path)
            logger.info(f"Successfully downloaded image to {permanent_path}")
            return permanent_path

    try:
        return await retry_with_backoff(_download)
    except Exception as e:
        logger.error(f"Error downloading image {url}: {e}")
        return None

async def cleanup_temp_dir(temp_dir):
    """Clean up temporary directory with error handling."""
    try:
        if os.path.exists(temp_dir):
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, functools.partial(shutil.rmtree, temp_dir, ignore_errors=True))
            logger.debug(f"Cleaned up temporary directory: {temp_dir}")
    except Exception as cleanup_error:
        logger.error(f"Error cleaning up temp directory {temp_dir}: {cleanup_error}")

async def process_instagram_image(url):
    """Process Instagram image with comprehensive error handling and validation."""
    if not url.startswith("https://www.instagram.com/"):
        logger.warning(f"Invalid Instagram URL: {url}")
        return []

    logger.info(f"Processing Instagram URL: {url}")
    image_paths = []
    temp_dir = tempfile.mkdtemp()

    try:
        # Add rate limiting delay
        await asyncio.sleep(RATE_LIMIT_DELAY)

        async with aiohttp.ClientSession() as session:
            if "/p/" in url:
                shortcode = url.split("/p/")[1].split("/")[0]
                post = await get_post(shortcode)

                nodes = post.get_sidecar_nodes() if hasattr(post, 'get_sidecar_nodes') else [post]
                
                tasks = []
                for idx, node in enumerate(nodes):
                    if not node.is_video:
                        image_url = node.display_url
                        filename = sanitize_filename(f"{post.owner_username}_{shortcode}_{idx}.png")
                        temp_path = os.path.join(temp_dir, filename)
                        final_path = os.path.join(DOWNLOAD_DIR, filename)

                        if os.path.exists(final_path):
                            logger.info(f"File already exists: {final_path}")
                            image_paths.append(final_path)
                            continue

                        tasks.append(download_image(session, image_url, temp_path, final_path))
                    else:
                        logger.info(f"Skipping video node {idx}")

                results = await asyncio.gather(*tasks, return_exceptions=True)
                image_paths.extend([res for res in results if isinstance(res, str)])

            elif "/stories/" in url:
                username = url.split("/stories/")[1].split("/")[0]
                story_image_urls = await get_story_images(username)

                tasks = []
                for idx, image_url in enumerate(story_image_urls):
                    filename = sanitize_filename(f"{username}_story_{idx}.png")
                    temp_path = os.path.join(temp_dir, filename)
                    final_path = os.path.join(DOWNLOAD_DIR, filename)

                    if os.path.exists(final_path):
                        logger.info(f"File already exists: {final_path}")
                        image_paths.append(final_path)
                        continue

                    tasks.append(download_image(session, image_url, temp_path, final_path))

                results = await asyncio.gather(*tasks, return_exceptions=True)
                image_paths.extend([res for res in results if isinstance(res, str)])

            else:
                logger.warning("Unrecognized Instagram URL format")
                return []

            logger.info(f"Successfully processed {len(image_paths)} images")
            return image_paths

    except instaloader.exceptions.InstaloaderException as e:
        logger.error(f"Instagram API error: {e}")
        return []
    except Exception as e:
        logger.error(f"Error processing Instagram image: {e}")
        return []
    finally:
        await cleanup_temp_dir(temp_dir)

# Initialize session on module load
try:
    initialize_instagram_session()
except Exception as e:
    logger.error(f"Failed to initialize Instagram session on startup: {e}")