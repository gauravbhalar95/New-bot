import os
import mimetypes
from utils.sanitize import sanitize_filename  # External sanitize function import

def get_file_extension(file_path):
    """Get the correct file extension based on MIME type."""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        return mimetypes.guess_extension(mime_type) or ''
    
    return file_path.split(".")[-1].split("?")[0]  # Extract from URL

def rename_files_in_directory(directory):
    """Rename all files in the specified directory sequentially."""
    if not os.path.exists(directory):
        return {}

    renamed_files = {}
    files = sorted([f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))])

    for index, filename in enumerate(files, start=1):
        old_path = os.path.join(directory, filename)
        _, ext = os.path.splitext(filename)

        if not ext:
            ext = get_file_extension(old_path)
            if not ext:
                ext = ".unknown"

        new_filename = f"file{index}{ext}"
        new_filename = sanitize_filename(new_filename)  # Sanitize filename
        new_path = os.path.join(directory, new_filename)

        if old_path != new_path:
            try:
                os.rename(old_path, new_path)
                renamed_files[filename] = new_filename
            except Exception as e:
                print(f"Error renaming '{filename}': {e}")

    return renamed_files