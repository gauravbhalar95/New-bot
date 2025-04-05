import os
import tempfile
import aiofiles
import asyncio
import aiohttp
import shutil
import functools
import instaloader
from config import DOWNLOAD_DIR, INSTAGRAM_USERNAME
from utils.sanitize import sanitize_filename
from utils.logger import logging

# Assuming logger, sanitize_filename, 
# are defined elsewhere as in your original code.
# Example placeholders for missing parts:

 Replace if needed
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

class MockLogger: # Simple logger mock for demonstration
    def info(self, msg): print(f"INFO: {msg}")
    def warning(self, msg): print(f"WARNING: {msg}")
    def error(self, msg): print(f"ERROR: {msg}")
logger = MockLogger()



# --- Instaloader setup code from your original snippet ---
INSTALOADER_INSTANCE = instaloader.Instaloader(
    download_videos=False, # Still keep this, good practice
    download_video_thumbnails=False,
    download_geotags=False,
    save_metadata=False,
    download_comments=False,
    post_metadata_txt_pattern=''
)

def initialize_instagram_session():
    # Simplified for demonstration - replace with your original if needed
    logger.info("Skipping session load for this example modification.")
    # try:
    #     if os.path.exists("instagram_cookies.txt"):
    #         INSTALOADER_INSTANCE.load_session_from_file(INSTAGRAM_USERNAME, "instagram_cookies.txt")
    #         logger.info("Instagram session loaded successfully")
    #     else:
    #         logger.warning("Instagram cookies file not found, operating without login")
    # except Exception as e:
    #     logger.error(f"Failed to load Instagram session: {e}")
    #     logger.info("Continuing without Instagram login")

try:
    initialize_instagram_session()
except Exception as e:
    logger.error(f"Instagram session initialization error: {e}")

async def get_post(shortcode):
    loop = asyncio.get_event_loop()
    # Ensure context is available, might need login for private posts
    if not INSTALOADER_INSTANCE.context.is_logged_in:
         logger.warning("Instaloader context not logged in, might fail for private posts.")
    return await loop.run_in_executor(
        None, functools.partial(instaloader.Post.from_shortcode, INSTALOADER_INSTANCE.context, shortcode)
    )
# --- End of Instaloader setup ---

# --- Utility functions download_image and cleanup_temp_dir from original ---
async def download_image(session, url, temp_path, permanent_path):
    try:
        async with session.get(url) as response:
            response.raise_for_status() # Raise an error for bad status codes
            async with aiofiles.open(temp_path, 'wb') as f:
                await f.write(await response.read())

            # Use asyncio's file operations for better async handling if possible
            # Using shutil.copy for simplicity here as os.rename might fail across devices
            # Consider aiofiles for async copy if needed, or run shutil in executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.copy, temp_path, permanent_path)

            # Original subprocess way:
            # proc = await asyncio.create_subprocess_exec(
            #     'cp', temp_path, permanent_path,
            #     stdout=asyncio.subprocess.PIPE,
            #     stderr=asyncio.subprocess.PIPE
            # )
            # stdout, stderr = await proc.communicate()
            # if proc.returncode != 0:
            #     logger.error(f"Failed to copy file: {stderr.decode()}")
            #     return None


            logger.info(f"Downloaded image to {permanent_path}")
            return permanent_path
    except aiohttp.ClientResponseError as e:
        logger.error(f"HTTP Error downloading image {url}: {e.status} {e.message}")
        return None
    except Exception as e:
        logger.error(f"Error downloading image {url}: {e}")
        return None

async def cleanup_temp_dir(temp_dir):
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, shutil.rmtree, temp_dir, ignore_errors=True)
        # logger.info(f"Cleaned up temp directory: {temp_dir}") # Optional: log cleanup
    except Exception as cleanup_error:
        logger.error(f"Error cleaning up temp directory {temp_dir}: {cleanup_error}")
# --- End of utility functions ---


# --- MODIFIED FUNCTION ---
async def process_instagram_image(url):
    """Process Instagram photo posts and return local file paths asynchronously.
       Downloads only items explicitly marked as non-videos.
    """
    if not url.startswith("https://www.instagram.com/"):
        logger.warning(f"Not an Instagram URL: {url}")
        return []

    shortcode = None
    if "/p/" in url:
        shortcode = url.split("/p/")[1].split("/")[0]
    elif "/reel/" in url: # Handle reels potentially if needed, though goal is images
         shortcode = url.split("/reel/")[1].split("/")[0]
         # logger.warning(f"URL is an Instagram Reel, attempting to get cover image if logic allows: {url}")
         # If you strictly want only /p/ posts, uncomment below
         # logger.warning(f"URL is an Instagram Reel, skipping: {url}")
         # return []
    else:
        logger.warning(f"Not a standard Instagram post or reel URL structure: {url}")
        return []

    if not shortcode:
        logger.warning(f"Could not extract shortcode from URL: {url}")
        return []

    try:
        post = await get_post(shortcode)
        image_paths = []
        temp_dir = tempfile.mkdtemp()

        try:
            # Determine nodes (items in the post)
            if post.typename == 'GraphSidecar':
                nodes = post.get_sidecar_nodes()
            elif post.typename == 'GraphImage':
                 nodes = [post] # Single image post
            elif post.typename == 'GraphVideo':
                 nodes = [post] # Single video post (will be skipped by logic below)
                 logger.info(f"Post {shortcode} is a video, skipping download.")
            else:
                 logger.warning(f"Post {shortcode} has unknown typename: {post.typename}, attempting to process as single node.")
                 nodes = [post] # Try processing as a single node


            async with aiohttp.ClientSession() as session:
                download_tasks = []

                for idx, node in enumerate(nodes):
                    # --- MODIFIED LOGIC ---
                    # Only download if the node is explicitly NOT a video.
                    if not node.is_video:
                        image_url = node.display_url
                        # Create a unique filename, sanitize it
                        filename_base = f"{post.owner_username}_{shortcode}_{idx}" if post.owner_username else f"{shortcode}_{idx}"
                        filename = sanitize_filename(f"{filename_base}.jpg")
                        temp_path = os.path.join(temp_dir, filename)
                        permanent_path = os.path.join(DOWNLOAD_DIR, filename)

                        # Avoid redownloading if it already exists (optional)
                        if os.path.exists(permanent_path):
                             logger.info(f"File already exists, skipping download: {permanent_path}")
                             image_paths.append(permanent_path)
                             continue

                        logger.info(f"Attempting to download image for node {idx} from {shortcode} (URL: {image_url})")
                        download_tasks.append(
                            download_image(session, image_url, temp_path, permanent_path)
                        )
                    else:
                         # Log skipped video nodes for clarity
                         logger.info(f"Skipping node {idx} from {shortcode} because it is a video (is_video=True).")
                    # --- END OF MODIFIED LOGIC ---

                if download_tasks:
                    results = await asyncio.gather(*download_tasks, return_exceptions=True)

                    for result in results:
                        if isinstance(result, Exception):
                            # Error already logged in download_image
                            pass
                        elif result: # Append successful permanent path
                            image_paths.append(result)

            return image_paths

        finally:
            # Ensure cleanup happens even if errors occur within the try block
            await cleanup_temp_dir(temp_dir)

    except instaloader.exceptions.InstaloaderException as e:
         logger.error(f"Instaloader error processing shortcode {shortcode}: {e}")
         return []
    except Exception as e:
        logger.error(f"General error in Instagram image handler for {url}: {e}")
        # Clean up temp dir if it was created before the error
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
             await cleanup_temp_dir(temp_dir)
        return []

# --- Example Usage ---
async def main():
    # Replace with a real Instagram post URL containing only images or mixed content
    test_url = "https://www.instagram.com/p/C5Zkx9ySf4E/" # Example URL (check content type)
    print(f"Processing URL: {test_url}")
    paths = await process_instagram_image(test_url)
    if paths:
        print("Downloaded images:")
        for path in paths:
            print(f"- {path}")
    else:
        print("No images downloaded (either none found, post is video-only, or an error occurred).")

if __name__ == "__main__":
    # Setup asyncio event loop
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Process interrupted by user.")
