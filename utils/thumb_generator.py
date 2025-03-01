import os
import logging
import asyncio
from PIL import Image
from moviepy import VideoFileClip  # ✅ Correct import
from utils.logger import setup_logging

# ✅ Logger Initialization
logger = setup_logging(logging.DEBUG)

# ✅ Thumbnail Directory
THUMBNAIL_DIR = "thumbnails"
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

def extract_frame(video_path, time=5):
    """
    Extracts a frame from the video at a given timestamp.
    """
    try:
        with VideoFileClip(video_path) as clip:  # ✅ Ensure proper closing
            frame_time = min(time, clip.duration - 0.1)  # Avoid out-of-range issue
            frame = clip.get_frame(frame_time)
            return Image.fromarray(frame)  # Convert frame to PIL Image
    except Exception as e:
        logger.error(f"⚠️ Error extracting frame: {e}")
        return None

async def generate_thumbnail(video_path, size=(3840, 2160)):
    """
    Asynchronously generate a high-definition thumbnail for the given video.
    
    :param video_path: Path to the video file.
    :param size: Thumbnail size (width, height). Default is 4K resolution (3840x2160).
    :return: Path to the generated thumbnail or None on failure.
    """
    try:
        loop = asyncio.get_running_loop()

        # ✅ Extract frame in a separate thread
        frame = await loop.run_in_executor(None, extract_frame, video_path)

        if frame is None:
            logger.error("❌ Failed to extract frame.")
            return None

        # ✅ Generate thumbnail path
        thumb_path = os.path.join(THUMBNAIL_DIR, os.path.basename(video_path) + ".jpg")

        # ✅ Resize & Save in a separate thread
        def resize_and_save():
            frame.resize(size, Image.LANCZOS).save(thumb_path, "JPEG", quality=95)

        await loop.run_in_executor(None, resize_and_save)

        logger.info(f"✅ HD Thumbnail saved at: {thumb_path}")
        return thumb_path

    except Exception as e:
        logger.error(f"⚠️ Failed to generate thumbnail: {e}")
        return None