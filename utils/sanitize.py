import re
import os

def is_valid_url(filename, max_length=250):
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
    
    # Trim the filename to the max_length
    if len(filename) > max_length:
        base, ext = os.path.splitext(filename)
        filename = base[:max_length - len(ext)] + ext

    return filename