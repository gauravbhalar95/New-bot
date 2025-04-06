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

async def get_story_images(username):
    try:
        loop = asyncio.get_event_loop()
        profile = await loop.run_in_executor(None, lambda: instaloader.Profile.from_username(INSTALOADER_INSTANCE.context, username))
        stories = await loop.run_in_executor(None, lambda: INSTALOADER_INSTANCE.get_stories(userids=[profile.userid]))

        image_urls = []
        for story in stories:
            for item in story.get_items():
                if not item.is_video:
                    image_urls.append(item.url)

        return image_urls
    except Exception as e:
        logger.error(f"Error fetching stories for {username}: {e}")
        return []

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
        await loop.run_in_executor(None, functools.partial(shutil.rmtree, temp_dir, ignore_errors=True))
    except Exception as cleanup_error:
        logger.error(f"Error cleaning up temp directory {temp_dir}: {cleanup_error}")

async def process_instagram_image(url):
    if not url.startswith("https://www.instagram.com/"):
        logger.warning(f"Invalid Instagram URL: {url}")
        return []

    image_paths = []
    temp_dir = tempfile.mkdtemp()
    async with aiohttp.ClientSession() as session:
        try:
            if "/p/" in url:
                shortcode = url.split("/p/")[1].split("/")[0]
                post = await get_post(shortcode)

                if hasattr(post, 'get_sidecar_nodes'):
                    nodes = post.get_sidecar_nodes()
                else:
                    nodes = [post]

                tasks = []
                for idx, node in enumerate(nodes):
                    if not node.is_video:
                        image_url = node.url
                        filename = sanitize_filename(f"{post.owner_username}_{shortcode}_{idx}.png")
                        temp_path = os.path.join(temp_dir, filename)
                        final_path = os.path.join(DOWNLOAD_DIR, filename)

                        if os.path.exists(final_path):
                            logger.info(f"File already exists: {final_path}")
                            image_paths.append(final_path)
                            continue

                        tasks.append(download_image(session, image_url, temp_path, final_path))
                    else:
                        logger.info(f"Skipping video node {idx}.")

                results = await asyncio.gather(*tasks)
                image_paths.extend([res for res in results if res])

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

                results = await asyncio.gather(*tasks)
                image_paths.extend([res for res in results if res])

            else:
                logger.warning("Unrecognized Instagram URL format.")
                return []

            return image_paths

        except Exception as e:
            logger.error(f"Error processing Instagram image: {e}")
            return []

        finally:
            await cleanup_temp_dir(temp_dir)