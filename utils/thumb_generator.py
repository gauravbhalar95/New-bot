import os
import logging
import asyncio
from PIL import Image
from moviepy.editor import VideoFileClip
from utils.logger import setup_logging

# ✅ Logger Initialization
logger = setup_logging(logging.DEBUG)

# ✅ Thumbnail Directory
THUMBNAIL_DIR = "thumbnails"
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

async def generate_thumbnail(video_path, size=(3840, 2160)):
    """
    Asynchronously generate a high-definition thumbnail for the given video.
    
    :param video_path: Path to the video file.
    :param size: Thumbnail size (width, height). Default is 4K resolution (3840x2160).
    :return: Path to the generated thumbnail.
    """
    try:
        loop = asyncio.get_running_loop()
        
        # ✅ Load video asynchronously
        clip = await loop.run_in_executor(None, VideoFileClip, video_path)
        
        # ✅ Capture frame at 5s (or first frame if shorter)
        frame = await loop.run_in_executor(None, clip.get_frame, min(5, clip.duration))
        
        # ✅ Convert frame to image
        thumb_path = os.path.join(THUMBNAIL_DIR, os.path.basename(video_path) + ".jpg")
        
        img = await loop.run_in_executor(None, Image.fromarray, frame)

        # ✅ Resize asynchronously
        img = await loop.run_in_executor(None, img.resize, size, Image.LANCZOS)

        # ✅ Save with high quality
        await loop.run_in_executor(None, img.save, thumb_path, "JPEG", 95)

        logger.info(f"✅ HD Thumbnail saved at: {thumb_path}")
        return thumb_path

    except Exception as e:
        logger.error(f"⚠️ Failed to generate thumbnail: {e}")
        return None

# ✅ Async Main Function for Testing
async def main():
    video_path = "sample_video.mp4"  # Change to your video path
    thumbnail = await generate_thumbnail(video_path)
    if thumbnail:
        print(f"✅ Thumbnail Generated: {thumbnail}")
    else:
        print("❌ Thumbnail generation failed!")

if __name__ == "__main__":
    asyncio.run(main())  # Run the async function