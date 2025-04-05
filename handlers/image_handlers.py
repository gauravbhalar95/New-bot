import os
import tempfile
import aiofiles
import asyncio
import aiohttp
import instaloader
from utils.logger import logger
from utils.sanitize import sanitize_filename
from utils.file_server import get_direct_download_link
from config import DOWNLOAD_DIR, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, INSTAGRAM_FILE

# Create instaloader instance without loading the session initially
INSTALOADER_INSTANCE = instaloader.Instaloader(
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    save_metadata=False,
    download_comments=False,
    post_metadata_txt_pattern=''
)

# Define the session loading in a function so we can handle errors
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

# Try to initialize the session, but don't stop execution if it fails
try:
    initialize_instagram_session()
except Exception as e:
    logger.error(f"Instagram session initialization error: {e}")

async def process_instagram_image(url):
    """Process Instagram photo posts and return downloaded image paths asynchronously."""
    if not url.startswith("https://www.instagram.com/"):
        logger.warning(f"Not an Instagram URL: {url}")
        return []

    try:
        # Extract the shortcode from the URL
        if "/p/" in url:
            shortcode = url.split("/p/")[1].split("/")[0]
        else:
            logger.warning(f"Not a valid Instagram post URL: {url}")
            return []

        # Fetch the post - this is synchronous and can't be made async with the current instaloader API
        # We could consider moving this to a thread pool if needed
        post = instaloader.Post.from_shortcode(INSTALOADER_INSTANCE.context, shortcode)
        images = []

        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()

        try:
            # Handle both single posts and carousels
            nodes = post.get_sidecar_nodes() if post.typename == 'GraphSidecar' else [post]
            
            # Use an async HTTP client for downloading
            async with aiohttp.ClientSession() as session:
                # Process image nodes concurrently
                download_tasks = []
                
                for idx, node in enumerate(nodes):
                    if not node.is_video:  # Only download images, skip videos
                        image_url = node.display_url
                        filename = sanitize_filename(f"{shortcode}_{idx}.jpg")
                        filepath = os.path.join(temp_dir, filename)
                        permanent_path = os.path.join(DOWNLOAD_DIR, filename)
                        
                        # Add the download task
                        download_tasks.append(
                            download_image(session, image_url, filepath, permanent_path)
                        )
                
                # Wait for all downloads to complete
                if download_tasks:
                    results = await asyncio.gather(*download_tasks, return_exceptions=True)
                    
                    # Process results and collect successful downloads
                    for result in results:
                        if isinstance(result, Exception):
                            logger.error(f"Error downloading image: {result}")
                        elif result:
                            images.append(result)

            return images

        finally:
            # Clean up temp directory asynchronously
            await cleanup_temp_dir(temp_dir)

    except Exception as e:
        logger.error(f"Instagram image handler error: {e}")
        return []

async def download_image(session, url, temp_path, permanent_path):
    """Download an image asynchronously and save it to the given paths."""
    try:
        async with session.get(url) as response:
            if response.status == 200:
                # Save to temporary file
                async with aiofiles.open(temp_path, 'wb') as f:
                    await f.write(await response.read())
                
                # Copy to permanent location
                # We use asyncio.create_subprocess_exec for better async performance
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
    """Clean up temporary directory asynchronously."""
    try:
        for file in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, file)
            proc = await asyncio.create_subprocess_exec(
                'rm', file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
        
        proc = await asyncio.create_subprocess_exec(
            'rmdir', temp_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
    except Exception as cleanup_error:
        logger.error(f"Error cleaning up temp directory: {cleanup_error}")