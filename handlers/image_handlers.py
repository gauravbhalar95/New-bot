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
from config import DOWNLOAD_DIR, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD
from instagram_private_api import Client, ClientLoginError, ClientCookieExpiredError
from instagram_private_api_extensions import media

# Initialize Instaloader instance
INSTALOADER_INSTANCE = instaloader.Instaloader(
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    save_metadata=False,
    download_comments=False,
    post_metadata_txt_pattern=''
)

# Private API instance
private_api = None

async def get_private_api():
    """Initialize and return private Instagram API client."""
    global private_api
    if private_api is None:
        try:
            private_api = Client(
                INSTAGRAM_USERNAME,
                INSTAGRAM_PASSWORD,
                auto_patch=True,
                drop_incompat_keys=False
            )
            logger.info("Private Instagram API initialized successfully")
        except (ClientLoginError, ClientCookieExpiredError) as e:
            logger.error(f"Instagram login failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during Instagram login: {e}")
            return None
    return private_api

def initialize_instagram_session():
    """Initialize Instagram session using cookies if available."""
    logger.info("Initializing Instagram session...")
    try:
        if os.path.exists("instagram_cookies.txt"):
            INSTALOADER_INSTANCE.load_session_from_file(INSTAGRAM_USERNAME, "instagram_cookies.txt")
            logger.info("Instagram session loaded successfully")
        else:
            logger.warning("Instagram cookies file not found, continuing without login")
    except Exception as e:
        logger.error(f"Failed to load Instagram session: {e}")

# Initialize session on module load
initialize_instagram_session()

async def get_post(shortcode):
    """Get Instagram post by shortcode."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, 
        functools.partial(instaloader.Post.from_shortcode, INSTALOADER_INSTANCE.context, shortcode)
    )

async def download_image(session, url, temp_path, permanent_path):
    """Download image from URL to temporary and permanent locations."""
    try:
        async with session.get(url) as response:
            if response.status == 200:
                async with aiofiles.open(temp_path, 'wb') as f:
                    await f.write(await response.read())
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(permanent_path), exist_ok=True)
                
                # Copy from temp to permanent location
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, shutil.copy, temp_path, permanent_path)
                logger.info(f"Downloaded image to {permanent_path}")
                return permanent_path
            else:
                logger.error(f"Failed to download image, status: {response.status}")
                return None
    except Exception as e:
        logger.error(f"Error downloading image {url}: {e}")
        return None

async def cleanup_temp_dir(temp_dir):
    """Clean up temporary directory."""
    try:
        if os.path.exists(temp_dir):
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, functools.partial(shutil.rmtree, temp_dir, ignore_errors=True))
    except Exception as cleanup_error:
        logger.error(f"Error cleaning up temp directory {temp_dir}: {cleanup_error}")

async def process_instagram_image(url):
    """Process Instagram image URL and return list of downloaded image paths."""
    if not url.startswith("https://www.instagram.com/"):
        logger.warning(f"Invalid Instagram URL: {url}")
        return []

    image_paths = []
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Get private API instance for restricted content
        api = await get_private_api()
        
        async with aiohttp.ClientSession() as session:
            if "/p/" in url:
                shortcode = url.split("/p/")[1].split("/")[0]
                
                try:
                    # Try regular Instaloader first
                    try:
                        post = await get_post(shortcode)
                        if hasattr(post, 'get_sidecar_nodes'):
                            nodes = post.get_sidecar_nodes()
                        else:
                            nodes = [post]

                        tasks = []
                        for idx, node in enumerate(nodes):
                            if not node.is_video:
                                image_url = node.display_url
                                filename = sanitize_filename(f"{post.owner_username}_{shortcode}_{idx}.jpg")
                                temp_path = os.path.join(temp_dir, filename)
                                final_path = os.path.join(DOWNLOAD_DIR, filename)

                                if os.path.exists(final_path):
                                    logger.info(f"File already exists: {final_path}")
                                    image_paths.append(final_path)
                                    continue

                                tasks.append(download_image(session, image_url, temp_path, final_path))
                            else:
                                logger.info(f"Skipping video node {idx}")

                    except Exception as e:
                        logger.info(f"Regular fetch failed, trying private API: {e}")
                        if api:
                            # Use private API for restricted content
                            media_id = api.media_id(shortcode)
                            post_info = api.media_info(media_id)['items'][0]
                            
                            if post_info.get('carousel_media'):
                                nodes = post_info['carousel_media']
                            else:
                                nodes = [post_info]
                            
                            tasks = []
                            for idx, node in enumerate(nodes):
                                if node.get('video_versions'):
                                    continue
                                    
                                image_versions = node.get('image_versions2', {}).get('candidates', [])
                                if not image_versions:
                                    continue
                                    
                                image_url = max(image_versions, key=lambda x: x.get('width', 0))['url']
                                filename = sanitize_filename(f"{post_info['user']['username']}_{shortcode}_{idx}.jpg")
                                temp_path = os.path.join(temp_dir, filename)
                                final_path = os.path.join(DOWNLOAD_DIR, filename)

                                if os.path.exists(final_path):
                                    image_paths.append(final_path)
                                    continue

                                tasks.append(download_image(session, image_url, temp_path, final_path))

                    if tasks:
                        results = await asyncio.gather(*tasks)
                        image_paths.extend([res for res in results if res])
                    
                except Exception as e:
                    logger.error(f"Error processing post {shortcode}: {e}")
                    return []

            elif "/stories/" in url:
                username = url.split("/stories/")[1].split("/")[0]
                try:
                    if api:
                        # Use private API for stories
                        user_info = api.username_info(username)
                        user_id = user_info['user']['pk']
                        stories = api.user_story_feed(user_id)
                        
                        tasks = []
                        for idx, item in enumerate(stories.get('reel', {}).get('items', [])):
                            if item.get('video_versions'):
                                continue
                                
                            image_versions = item.get('image_versions2', {}).get('candidates', [])
                            if not image_versions:
                                continue
                                
                            image_url = max(image_versions, key=lambda x: x.get('width', 0))['url']
                            filename = sanitize_filename(f"{username}_story_{idx}.jpg")
                            temp_path = os.path.join(temp_dir, filename)
                            final_path = os.path.join(DOWNLOAD_DIR, filename)

                            if os.path.exists(final_path):
                                image_paths.append(final_path)
                                continue

                            tasks.append(download_image(session, image_url, temp_path, final_path))

                        if tasks:
                            results = await asyncio.gather(*tasks)
                            image_paths.extend([res for res in results if res])
                    
                except Exception as e:
                    logger.error(f"Error fetching stories for {username}: {e}")
                    return []

            else:
                logger.warning("Unrecognized Instagram URL format")
                return []

            return image_paths

    except Exception as e:
        logger.error(f"Error processing Instagram image: {e}")
        return []

    finally:
        await cleanup_temp_dir(temp_dir)