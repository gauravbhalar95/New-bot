import re
import os
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def sanitize_filename(filename, max_length=250):
    """
    Synchronously removes special characters from the filename and trims it to a maximum length.

    Args:
        filename (str): The original filename.
        max_length (int): Maximum allowed length for the filename.

    Returns:
        str: The sanitized filename.
    """
    clean_name = re.sub(r'[\\/*?:"<>|]', '_', filename).strip()
    clean_name = re.sub(r'[^\x00-\x7F]+', '', clean_name)  # Remove non-ASCII characters
    base, ext = os.path.splitext(clean_name)
    if len(base) > max_length - len(ext):
        base = base[:max_length - len(ext)]
    return base + ext


async def sanitize_filename_async(filename, max_length=250):
    """
    Asynchronously removes special characters from the filename and trims it to a maximum length.

    Args:
        filename (str): The original filename.
        max_length (int): Maximum allowed length for the filename.

    Returns:
        str: The sanitized filename.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, sanitize_filename, filename, max_length)