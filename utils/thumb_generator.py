import os
import logging
from PIL import Image

# ✅ Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ✅ Thumbnail directory
THUMBNAIL_DIR = "thumbnails"
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

def generate_thumbnail(video_path, size=(320, 180)):
    """
    Generate a thumbnail for the given video and save it as an image.
    :param video_path: Path to the video file.
    :param size: Thumbnail size (width, height).
    :return: Path to the generated thumbnail.
    """
    try:
        from moviepy import VideoFileClip

        # ✅ Load video
        clip = VideoFileClip(video_path)

        # ✅ Capture thumbnail at 5s (or first frame if shorter)
        frame = clip.get_frame(min(5, clip.duration))

        # ✅ Convert frame to image
        thumb_path = os.path.join(THUMBNAIL_DIR, os.path.basename(video_path) + ".jpg")
        img = Image.fromarray(frame)
        img.thumbnail(size)
        img.save(thumb_path, "JPEG")

        logger.info(f"✅ Thumbnail saved: {thumb_path}")
        return thumb_path

    except Exception as e:
        logger.error(f"❌ Failed to generate thumbnail: {e}")
        return None