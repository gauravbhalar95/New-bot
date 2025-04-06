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

INSTALOADER_INSTANCE = instaloader.Instaloader(
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    save_metadata=False,
    download_comments=False,
    post_metadata_txt_pattern=''
)

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "top_deals_station")

def initialize_instagram_session():
    logger.info("Initializing Instagram session...")
    try:
        if os.path.exists("instagram_cookies.txt"):
            INSTALOADER_INSTANCE.load_session_from_file(INSTAGRAM_USERNAME, "instagram_cookies.txt")
            logger.info("Instagram session loaded successfully")
        else:
            logger.warning("Instagram cookies file not found, continuing without login")
    except Exception as e:
        logger.error(f"Failed to load Instagram session: {e}")

initialize_instagram_session()

async def get_post(shortcode):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(instaloader.Post.from_shortcode, INSTALOADER_INSTANCE.context, shortcode))

async def download_image(session, url, temp_path, permanent_path):
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            async with aiofiles.open(temp_path, 'wb') as f:
                await f.write(await response.read())
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.copy, temp_path, permanent_path)
            logger.info(f"Downloaded image to {permanent_path}")
            return permanent_path
    except Exception as e:
        logger.error(f"Error downloading image {url}: {e}")
        return None

async def cleanup_temp_dir(temp_dir):
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, shutil.rmtree, temp_dir, ignore_errors=True)
    except Exception as cleanup_error:
        logger.error(f"Error cleaning up temp directory {temp_dir}: {cleanup_error}")

def create_instagram_collage(image_paths, collage_path="collage.jpg"):
    try:
        images = [Image.open(p) for p in image_paths if os.path.exists(p)]
        if not images:
            return None
        widths, heights = zip(*(img.size for img in images))
        total_width = sum(widths)
        max_height = max(heights)
        collage = Image.new("RGB", (total_width, max_height), (255, 255, 255))
        x_offset = 0
        for img in images:
            collage.paste(img, (x_offset, 0))
            x_offset += img.width
        collage.save(collage_path)
        return collage_path
    except Exception as e:
        logger.error(f"Failed to create collage: {e}")
        return None

async def process_instagram_image(url):
    if not url.startswith("https://www.instagram.com/"):
        logger.warning(f"Invalid Instagram URL: {url}")
        return []

    shortcode = None
    if "/p/" in url:
        shortcode = url.split("/p/")[1].split("/")[0]
    elif "/reel/" in url:
        shortcode = url.split("/reel/")[1].split("/")[0]
    else:
        logger.warning(f"Unrecognized Instagram URL structure: {url}")
        return []

    if not shortcode:
        logger.warning("Shortcode not found.")
        return []

    try:
        post = await get_post(shortcode)
        image_paths = []
        temp_dir = tempfile.mkdtemp()

        try:
            if post.typename == 'GraphSidecar':
                nodes = post.get_sidecar_nodes()
            elif post.typename in ['GraphImage', 'GraphVideo']:
                nodes = [post]
            else:
                logger.warning(f"Unknown typename {post.typename}")
                nodes = [post]

            async with aiohttp.ClientSession() as session:
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

                        logger.info(f"Downloading image: {image_url}")
                        tasks.append(download_image(session, image_url, temp_path, final_path))
                    else:
                        logger.info(f"Skipping video node {idx}.")

                results = await asyncio.gather(*tasks)
                image_paths += [res for res in results if res]

            if len(image_paths) >= 2:
                collage_output = os.path.join(DOWNLOAD_DIR, f"{post.owner_username}_{shortcode}_collage.jpg")
                collage_path = create_instagram_collage(image_paths, collage_output)
                if collage_path:
                    logger.info(f"Collage created at: {collage_path}")
                    image_paths.append(collage_path)

            return image_paths

        finally:
            await cleanup_temp_dir(temp_dir)

    except Exception as e:
        logger.error(f"Error processing Instagram post: {e}")
        return []