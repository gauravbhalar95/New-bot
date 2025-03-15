import re
import os
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

async def sanitize_filename(filename, max_length=250):
    """
    Asynchronously removes special characters from the filename and trims it to a maximum length.

    Args:
        filename (str): The original filename.
        max_length (int): Maximum allowed length for the filename.

    Returns:
        str: The sanitized filename.
    """
    loop = asyncio.get_running_loop()

    def clean():
        clean_name = re.sub(r'[\\/*?:"<>|]', '_', filename).strip()
        clean_name = re.sub(r'[^\x00-\x7F]+', '', clean_name)

        base, ext = os.path.splitext(clean_name)
        if len(base) > max_length - len(ext):
            base = base[:max_length - len(ext)]
        return base + ext

    return await loop.run_in_executor(None, clean)

async def download_video(video_url, download_path):
    """
    Asynchronously downloads a video and ensures the filename is sanitized.

    Args:
        video_url (str): The URL of the video to download.
        download_path (str): The folder where the video will be saved.
    """
    try:
        filename = "Sachi Re Mari.f251.webm"  # Example filename from the downloader
        sanitized_name = await sanitize_filename(filename)

        # Ensure the download path exists
        os.makedirs(download_path, exist_ok=True)

        # Full path for saving the file
        file_path = os.path.join(download_path, sanitized_name)
        logging.debug(f"Downloading video to: {file_path}")

        # Simulate download logic
        await asyncio.sleep(1)  # Simulate download delay
        with open(file_path, 'w') as f:
            f.write("Sample video content")

        logging.info(f"✅ Video downloaded successfully: {file_path}")

    except Exception as e:
        logging.error(f"⚠️ Error downloading video: {e}")

if __name__ == "__main__":
    