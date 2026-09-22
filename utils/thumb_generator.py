import os
import logging
import asyncio
import cv2

from utils.logger import setup_logging

# Logger initialization
logger = setup_logging(logging.DEBUG)

# Thumbnail directory
THUMBNAIL_DIR = "thumbnails"
os.makedirs(THUMBNAIL_DIR, exist_ok=True)


def extract_frame(video_path, time=5):
    """Extract a video frame at the specified timestamp."""

    cap = None

    try:
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            logger.error(f"❌ Cannot open video: {video_path}")
            return None

        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)

        if fps <= 0 or frame_count <= 0:
            logger.error("❌ Invalid video FPS or frame count.")
            return None

        duration = frame_count / fps

        # Prevent seeking past the end of the video
        frame_time = min(time, max(0, duration - 0.1))

        frame_number = int(frame_time * fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        success, frame = cap.read()

        if not success:
            logger.error("❌ Failed to read video frame.")
            return None

        return frame

    except Exception as e:
        logger.error(f"⚠️ Error extracting frame: {e}")
        return None

    finally:
        if cap is not None:
            cap.release()


async def generate_thumbnail(video_path, size=(3840, 2160)):
    """Generate an HD thumbnail from a video."""

    try:
        loop = asyncio.get_running_loop()

        # Extract frame in a background thread
        frame = await loop.run_in_executor(
            None,
            extract_frame,
            video_path
        )

        if frame is None:
            logger.error("❌ Failed to extract frame.")
            return None

        thumb_path = os.path.join(
            THUMBNAIL_DIR,
            os.path.basename(video_path) + ".jpg"
        )

        def resize_and_save():
            try:
                resized = cv2.resize(
                    frame,
                    size,
                    interpolation=cv2.INTER_LANCZOS4
                )

                success = cv2.imwrite(
                    thumb_path,
                    resized,
                    [
                        cv2.IMWRITE_JPEG_QUALITY,
                        95
                    ]
                )

                if not success:
                    logger.error("❌ Failed to save thumbnail.")
                    return False

                return True

            except Exception as e:
                logger.error(f"❌ Error saving thumbnail: {e}")
                return False

        success = await loop.run_in_executor(
            None,
            resize_and_save
        )

        if not success:
            return None

        logger.info(
            f"✅ HD Thumbnail saved at: {thumb_path}"
        )

        return thumb_path

    except Exception as e:
        logger.error(
            f"⚠️ Failed to generate thumbnail: {e}"
        )
        return None