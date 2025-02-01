import re

def sanitize_filename(filename, max_length=250):
    """
    Sanitizes a filename by removing invalid characters and limiting its length.

    :param filename: The original filename.
    :param max_length: The maximum allowed length for the filename.
    :return: A sanitized and trimmed filename.
    """
    # Remove invalid characters
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)

    # Trim whitespace and enforce max length
    return filename.strip()[:max_length]
