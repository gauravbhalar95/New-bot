import os
import tempfile
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
    """Process Instagram photo posts and return downloaded image paths."""
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
            
        # Fetch the post
        post = instaloader.Post.from_shortcode(INSTALOADER_INSTANCE.context, shortcode)
        images = []

        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Handle both single posts and carousels
            nodes = post.get_sidecar_nodes() if post.typename == 'GraphSidecar' else [post]
            
            for idx, node in enumerate(nodes):
                if not node.is_video:  # Only download images, skip videos
                    image_url = node.display_url
                    filename = sanitize_filename(f"{shortcode}_{idx}.jpg")
                    filepath = os.path.join(temp_dir, filename)

                    # Download the image
                    INSTALOADER_INSTANCE.context.get_and_write_raw(node.display_url, filepath)
                    
                    # Copy to download directory
                    permanent_path = os.path.join(DOWNLOAD_DIR, filename)
                    os.system(f"cp {filepath} {permanent_path}")
                    images.append(permanent_path)
                    logger.info(f"Downloaded image to {permanent_path}")
            
            return images
            
        finally:
            # Clean up temp directory
            try:
                for file in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, file))
                os.rmdir(temp_dir)
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up temp directory: {cleanup_error}")

    except Exception as e:
        logger.error(f"Instagram image handler error: {e}")
        return []