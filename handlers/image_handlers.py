import os
import tempfile
import aiofiles
import asyncio
import aiohttp
import shutil
import functools
import instaloader

from utils.logger import logger
from utils.sanitize import sanitize_filename
from config import DOWNLOAD_DIR, INSTAGRAM_USERNAME

# Create instaloader instance without loading the session initially
INSTALOADER_INSTANCE = instaloader.Instaloader(
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    save_metadata=False,
    download_comments=False,
    post_metadata_txt_pattern=''
)

def initialize_instagram_session():
    try:
        if os.path.exists("instagram_cookies.txt"):
            INSTALOADER_INSTANCE.load_session_from_file(INSTAGRAM_USERNAME, "instagram_cookies.txt")
            logger.info("Instagram session loaded successfully")
        else:
            logger.warning("Instagram cookies file not found, operating without login")
    except Exception as e:
        logger.error(f"Failed to load Instagram session: {e}")
        logger.info("Continuing without Instagram login")

# Try to initialize the session
try:
    initialize_instagram_session()
except Exception as e:
    logger.error(f"Instagram session initialization error: {e}")

async def get_post(shortcode):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, functools.partial(instaloader.Post.from_shortcode, INSTALOADER_INSTANCE.context, shortcode)
    )

async def process_instagram_image(url):
    """Process Instagram photo posts and return local file paths asynchronously."""
    if not url.startswith("https://www.instagram.com/"):
        logger.warning(f"Not an Instagram URL: {url}")
        return []

    try:
        if "/p/" in url:
            shortcode = url.split("/p/")[1].split("/")[0]
        else:
            logger.warning(f"Not a valid Instagram post URL: {url}")
            return []

        post = await get_post(shortcode)
        image_paths = []
        temp_dir = tempfile.mkdtemp()

        try:
            nodes = post.get_sidecar_nodes() if post.typename == 'GraphSidecar' else [post]

            async with aiohttp.ClientSession() as session:
                download_tasks = []

                for idx, node in enumerate(nodes):
                    is_fake_video = node.is_video and getattr(node, 'video_duration', 0) == 0
                    if not node.is_video or is_fake_video:
                        image_url = node.display_url
                        filename = sanitize_filename(f"{shortcode}_{idx}.jpg")
                        temp_path = os.path.join(temp_dir, filename)
                        permanent_path = os.path.join(DOWNLOAD_DIR, filename)

                        download_tasks.append(
                            download_image(session, image_url, temp_path, permanent_path)
                        )

                if download_tasks:
                    results = await asyncio.gather(*download_tasks, return_exceptions=True)

                    for result in results:
                        if isinstance(result, Exception):
                            logger.error(f"Error downloading image: {result}")
                        elif result:
                            image_paths.append(result)

            return image_paths

        finally:
            await cleanup_temp_dir(temp_dir)

    except Exception as e:
        logger.error(f"Instagram image handler error: {e}")
        return []

async def download_image(session, url, temp_path, permanent_path):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                async with aiofiles.open(temp_path, 'wb') as f:
                    await f.write(await response.read())

                proc = await asyncio.create_subprocess_exec(
                    'cp', temp_path, permanent_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()

                logger.info(f"Downloaded image to {permanent_path}")
                return permanent_path
            else:
                logger.error(f"Failed to download image, status code: {response.status}")
                return None
    except Exception as e:
        logger.error(f"Error downloading image: {e}")
        return None

async def cleanup_temp_dir(temp_dir):
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, shutil.rmtree, temp_dir)
    except Exception as cleanup_error:
        logger.error(f"Error cleaning up temp directory: {cleanup_error}")