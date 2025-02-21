import os

def rename_files_in_directory(directory):
    """
    Renames all files in the specified directory sequentially.
    Returns a dictionary mapping old filenames to new filenames.

    Args:
        directory (str): The directory containing files to be renamed.

    Returns:
        dict: A dictionary where keys are old filenames and values are new filenames.
    """
    if not os.path.exists(directory):
        print(f"❌ Directory '{directory}' not found!")
        return {}

    renamed_files = {}  # Dictionary to store renamed files
    files = sorted([f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))])

    for index, filename in enumerate(files, start=1):
        old_path = os.path.join(directory, filename)
        _, ext = os.path.splitext(filename)  # Extract file extension
        new_filename = f"file{index}{ext}"  # New name format: file1.txt, file2.jpg
        new_path = os.path.join(directory, new_filename)

        if old_path != new_path:
            try:
                os.rename(old_path, new_path)
                renamed_files[filename] = new_filename
                print(f"✅ Renamed: '{filename}' → '{new_filename}'")
            except Exception as e:
                print(f"⚠️ Error renaming '{filename}': {e}")

    return renamed_files  # Return the mapping of old → new filenames

