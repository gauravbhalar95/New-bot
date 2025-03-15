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

# Example usage in an async function
async def main():
    # Test example
    original_filename = "example video??*<>|.mp4"
    sanitized_filename = await sanitize_filename(original_filename)
    logging.info(f"Original: {original_filename}")
    logging.info(f"Sanitized: {sanitized_filename}")

# Example usage in a sync function
def sync_function():
    original_filename = "example video??*<>|.mp4"
    sanitized_filename = asyncio.run(sanitize_filename(original_filename))
    print(f"Original: {original_filename}")
    print(f"Sanitized: {sanitized_filename}")

# Run the example
if __name__ == "__main__":
    # Async example
    asyncio.run(main())

    # Sync example
    sync_function()