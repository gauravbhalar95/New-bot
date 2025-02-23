import os
import logging
from PIL import Image
from utils.logger import setup_logging


# Initialize logger
logger = setup_logging(logging.DEBUG) #Example of setting to debug level.

# ✅ Thumbnail directory
THUMBNAIL_DIR = "thumbnails"
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

def generate_thumbnail(video_path, size=(3840, 2160)):
    """
    Generate a high-definition thumbnail for the given video and save it as an image.
    :param video_path: Path to the video file.
    :param size: Thumbnail size (width, height). Default is 4K resolution (3840x2160).
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

        # ✅ Resize the image to HD resolution and save with high quality
        img = img.resize(size, Image.LANCZOS)  # Ensure it gets resized to the HD resolution
        img.save(thumb_path, "JPEG", quality=95)  # Save with high quality

        logger.info(f"✅ HD Thumbnail saved at: {thumb_path}")
        return thumb_path

    except Exception as e:
        logger.error(f"⚠️ Failed to generate thumbnail: {e}")
        return None