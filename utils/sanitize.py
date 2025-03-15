import re
import os
import asyncio
import mimetypes
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
        # ✅ Replace invalid characters with an underscore
        clean_name = re.sub(r'[\\/*?:"<>|]', '_', filename)

        # ✅ Remove leading and trailing whitespace
        clean_name = clean_name.strip()

        # ✅ Remove Unicode non-ASCII characters (better compatibility)
        clean_name = re.sub(r'[^\x00-\x7F]+', '', clean_name)

        # ✅ Trim filename to max_length while keeping the extension
        base, ext = os.path.splitext(clean_name)
        if len(base) > max_length - len(ext):
            base = base[:max_length - len(ext)]
        return base + ext

    return await loop.run_in_executor(None, clean)

async def get_file_extension(file_path):
    """Asynchronously get the correct file extension based on MIME type."""
    loop = asyncio.get_running_loop()
    mime_type, _ = await loop.run_in_executor(None, mimetypes.guess_type, file_path)

    if mime_type:
        return mimetypes.guess_extension(mime_type) or ''

    return file_path.split(".")[-1].split("?")[0]  # Extract from URL

async def rename_file(old_path, new_path):
    """Asynchronously rename a file."""
    logging.debug(f"rename_file() called with: old_path={old_path}, new_path={new_path}")
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

    if not files:
        logging.info(f"No files found in directory: {directory}")
        return renamed_files

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
        else:
            logging.info(f"Skipping (already renamed): {old_path}")

    await asyncio.gather(*tasks)  # Run all rename operations concurrently
    return renamed_files

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python rename_files.py <directory>")
        sys.exit(1)

    directory = sys.argv[1]

    try:
        renamed_files = asyncio.run(rename_files_in_directory(directory))
        if renamed_files:
            print("Renamed files:")
            for old, new in renamed_files.items():
                print(f"{old} ➔ {new}")
        else:
            print("No files were renamed.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")