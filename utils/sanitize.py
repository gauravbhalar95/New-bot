import re

# Utility to sanitize filenames
def sanitize_filename(filename, max_length=250):
    """
    Removes special characters from the filename and trims it to a maximum length.
    
    Args:
        filename (str): The original filename.
        max_length (int): Maximum allowed length for the filename.

    Returns:
        str: The sanitized filename.
    """
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    return filename.strip()[:max_length]