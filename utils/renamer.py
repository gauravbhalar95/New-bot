import os
import mimetypes
import logging
from utils.sanitize import sanitize_filename  # External sanitize function import

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_file_extension(file_path):
    """Get the correct file extension based on MIME type."""
    mime_type, _ = mimetypes.guess_type(file_path)

    if mime_type:
        return mimetypes.guess_extension(mime_type) or ''

    return file_path.split(".")[-1].split("?")[0]  # Extract from URL

def rename_file(old_path, new_path):
    """Rename a file."""
    logging.debug(f"rename_file() called with: old_path={old_path}, new_path={new_path}")
    try:
        os.rename(old_path, new_path)
        logging.info(f"Renamed: {old_path} ➔ {new_path}")
    except Exception as e:
        logging.error(f"Failed to rename {old_path} ➔ {new_path}: {e}")

def rename_files_in_directory(directory):
    """Rename all files in the specified directory sequentially."""
    if not os.path.exists(directory):
        logging.warning(f"Directory not found: {directory}")
        return {}

    renamed_files = {}
    files = sorted([f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))])

    if not files:
        logging.info(f"No files found in directory: {directory}")
        return renamed_files

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
            rename_file(old_path, new_path)
            renamed_files[filename] = new_filename
        else:
            logging.info(f"Skipping (already renamed): {old_path}")

    return renamed_files

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python rename_files.py <directory>")
        sys.exit(1)

    directory = sys.argv[1]

    try:
        renamed_files = rename_files_in_directory(directory)
        if renamed_files:
            print("Renamed files:")
            for old, new in renamed_files.items():
                print(f"{old} ➔ {new}")
        else:
            print("No files were renamed.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
