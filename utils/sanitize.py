import re
import os
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
        clean_name = re.sub(r'[^\x00-\x7F]+', '', clean_name)  # Non-ASCII characters removed
        base, ext = os.path.splitext(clean_name)
        if len(base) > max_length - len(ext):
            base = base[:max_length - len(ext)]
        return base + ext

    return await loop.run_in_executor(None, clean)

# Example usage in an async function
async def async_example():
    original_filename = "example video??*<>|.mp4"
    sanitized_filename = await sanitize_filename(original_filename)
    logging.info(f"Original (async): {original_filename}")
    logging.info(f"Sanitized (async): {sanitized_filename}")

# Example usage in a sync function
def sync_example():
    original_filename = "example video??*<>|.mp4"
    sanitized_filename = asyncio.run(sanitize_filename(original_filename))
    logging.info(f"Original (sync): {original_filename}")
    logging.info(f"Sanitized (sync): {sanitized_filename}")

# Example integration with yt_dlp download logic
async def download_video(url):
    import yt_dlp
    ydl_opts = {'outtmpl': 'downloads/%(title)s.%(ext)s', 'format': 'bestvideo+bestaudio/best'}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        video_title = info_dict.get('title', 'Unknown Title')
        
        # Correct usage of sanitize_filename with await
        sanitized_title = await sanitize_filename(video_title)
        download_path = f"downloads/{sanitized_title}.mp4"

        logging.info(f"Downloaded: {download_path}")

# Run the examples
if __name__ == "__main__":
    asyncio.run(async_example())  # Async example
    sync_example()                # Sync example