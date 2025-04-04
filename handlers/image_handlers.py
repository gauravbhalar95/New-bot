import os
import tempfile
import instaloader
from telegram import Update
from telegram.ext import ContextTypes
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

async def process_instagram_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("https://www.instagram.com/p/"):
        return

    try:
        shortcode = url.split("/p/")[1].split("/")[0]
        post = instaloader.Post.from_shortcode(INSTALOADER_INSTANCE.context, shortcode)
        images = []

        with tempfile.TemporaryDirectory() as tmpdir:
            for idx, node in enumerate(post.get_sidecar_nodes() if post.typename == 'GraphSidecar' else [post]):
                image_url = node.display_url
                filename = sanitize_filename(f"{shortcode}_{idx}.jpg")
                filepath = os.path.join(tmpdir, filename)

                INSTALOADER_INSTANCE.context.get_and_write_raw(node.display_url, filepath)
                images.append(filepath)

            for img_path in images:
                file_link = generate_direct_download_link(img_path)
                await update.message.reply_photo(photo=open(img_path, "rb"), caption=f"[Direct Link]({file_link})", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Instagram image handler error: {e}")
        await update.message.reply_text("Failed to download Instagram image. Please try again.")