import re
import os
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def sanitize_filename(filename: str, max_length: int = 250) -> str:
    """
    Removes special characters from the filename and trims it to a maximum length.
    
    Args:
        filename (str): Original filename to sanitize.
        max_length (int): Maximum allowed length of the sanitized filename.

    Returns:
        str: Sanitized and trimmed filename.
    """
    clean_name = re.sub(r'[\\/*?:"<>|]', '_', filename).strip()
    clean_name = re.sub(r'[^\x00-\x7F]+', '', clean_name)
    base, ext = os.path.splitext(clean_name)
    if len(base) > max_length - len(ext):
        base = base[:max_length - len(ext)]
    return base + ext


async def sanitize_filename_async(filename: str, max_length: int = 250) -> str:
    """
    Asynchronously sanitizes the filename.

    Args:
        filename (str): Original filename to sanitize.
        max_length (int): Maximum allowed length of the sanitized filename.

    Returns:
        str: Sanitized and trimmed filename.
    """
    return await asyncio.to_thread(sanitize_filename, filename, max_length)


def sanitize_dropbox_path(path: str) -> str:
    """
    Sanitizes the Dropbox path by ensuring a leading slash and removing illegal characters.

    Args:
        path (str): Original Dropbox path.

    Returns:
        str: Sanitized Dropbox path.
    """
    if not path.startswith("/"):
        path = "/" + path
    path = re.sub(r'[\\?%*:|"<>]', "_", path)
    return path