import re
import os

def sanitize_filename(filename, max_length=250):
    """
    Removes special characters from the filename and trims it to a maximum length.

    Args:
        filename (str): The original filename.
        max_length (int): Maximum allowed length for the filename.

    Returns:
        str: The sanitized filename.
    """
    # Replace invalid characters with an underscore
    filename = re.sub(r'[\\/*?:"<>|]', '_', filename)

    # Remove leading and trailing whitespace
    filename = filename.strip()

    # Trim the filename to the max_length while preserving the extension
    base, ext = os.path.splitext(filename)
    if len(base) > max_length - len(ext):
        base = base[:max_length - len(ext)]
    filename = base + ext

    return filename
