import os
import tempfile
import instaloader
from utils.logger import logger
from utils.sanitize import sanitize_filename
from utils.file_server import generate_direct_download_link
from config import DOWNLOAD_DIR, INSTAGRAM_USERNAME, INSTAGRAM_PASSEORD, INSTAGRAM_FILE

INSTALOADER_INSTANCE = instaloader.Instaloader(
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    save_metadata=False,
    download_comments=False,
    post_metadata_txt_pattern=''
)

INSTALOADER_INSTANCE.load_session_from_file("INSTAGRAM_USERNAME", filename="instagram_cookies.txt")

async def process_instagram_image(url):
    """Process Instagram photo posts and return downloaded image paths."""
    if not url.startswith("https://www.instagram.com/p/"):
        return []

    try:
        shortcode = url.split("/p/")[1].split("/")[0]
        post = instaloader.Post.from_shortcode(INSTALOADER_INSTANCE.context, shortcode)
        images = []

        with tempfile.TemporaryDirectory() as tmpdir:
            # Handle both single posts and carousels
            nodes = post.get_sidecar_nodes() if post.typename == 'GraphSidecar' else [post]
            
            for idx, node in enumerate(nodes):
                if not node.is_video:  # Only download images, skip videos
                    image_url = node.display_url
                    filename = sanitize_filename(f"{shortcode}_{idx}.jpg")
                    filepath = os.path.join(tmpdir, filename)

                    # Download the image
                    INSTALOADER_INSTANCE.context.get_and_write_raw(node.display_url, filepath)
                    
                    # Copy to a permanent location for the bot to use
                    permanent_path = os.path.join(DOWNLOAD_DIR, filename)
                    os.system(f"cp {filepath} {permanent_path}")
                    images.append(permanent_path)

        logger.info(f"Downloaded {len(images)} images from Instagram post {shortcode}")
        return images

    except Exception as e:
        logger.error(f"Instagram image handler error: {e}")
        return []