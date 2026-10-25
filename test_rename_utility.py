"""Interactive input/output tester for utils.rename_utility.

Run from the repository root:
    python test_rename_utility.py

A temporary sample file is used, so no real downloads are renamed.
"""
from pathlib import Path
from tempfile import TemporaryDirectory

from utils.rename_utility import rename_downloaded_file


def main() -> None:
    input_name = input("Input filename (e.g. my_video.mp4): ").strip()
    if not input_name:
        print("Output: No filename entered.")
        return

    # Accept only a filename, not a user-supplied path.
    input_name = Path(input_name).name
    if input_name in {"", ".", ".."}:
        print("Output: Invalid filename.")
        return

    username = input("Username (optional, press Enter to skip): ").strip() or None
    source_url = input("Source URL (optional, press Enter to skip): ").strip() or None

    with TemporaryDirectory(prefix="rename-utility-test-") as temp_dir:
        input_path = Path(temp_dir) / input_name
        input_path.write_text("temporary rename utility test file", encoding="utf-8")

        output_path = rename_downloaded_file(
            str(input_path),
            username=username,
            source_url=source_url,
        )

        print(f"Input:  {input_name}")
        print(f"Output: {Path(output_path).name}")


if __name__ == "__main__":
    main()
