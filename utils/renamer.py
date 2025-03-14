import os
import mimetypes
import asyncio
from utils.sanitize import sanitize_filename  # External sanitize function import
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def get_file_extension(file_path):
    """Asynchronously get the correct file extension based on MIME type."""
    loop = asyncio.get_running_loop()
    mime_type, _ = await loop.run_in_executor(None, mimetypes.guess_type, file_path)

    if mime_type:
        return mimetypes.guess_extension(mime_type) or ''

    return file_path.split(".")[-1].split("?")[0]  # Extract from URL

async def rename_file(old_path, new_path):
    """Asynchronously rename a file."""
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, os.rename, old_path, new_path)
        logging.info(f"Renamed: {old_path} ➔ {new_path}")
    except Exception as e:
        logging.error(f"Failed to rename {old_path} ➔ {new_path}: {e}")

async def rename_files_in_directory(directory):
    """Asynchronously rename all files in the specified directory sequentially."""
    if not os.path.exists(directory):
        logging.warning(f"Directory not found: {directory}")
        return {}

    renamed_files = {}
    files = sorted([f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))])

    tasks = []
    for index, filename in enumerate(files, start=1):
        old_path = os.path.join(directory, filename)
        _, ext = os.path.splitext(filename)

        if not ext:
            ext = await get_file_extension(old_path)
            if not ext:
                ext = ".unknown"

        new_filename = f"file{index}{ext}"
        new_filename = sanitize_filename(new_filename)  # Sanitize filename
        new_path = os.path.join(directory, new_filename)

        if old_path != new_path:
            tasks.append(asyncio.create_task(rename_file(old_path, new_path)))
            renamed_files[filename] = new_filename

    await asyncio.gather(*tasks)  # Run all rename operations concurrently
    return renamed_files