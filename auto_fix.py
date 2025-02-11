import ast
import os
import logging
import subprocess

# Logging setup
logging.basicConfig(filename="fixer.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def check_syntax(filename):
    """Check if the Python file has syntax errors."""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            source = f.read()
        ast.parse(source)  # Parse the source code
        logging.info(f"✅ No syntax errors found in {filename}")
        return True
    except SyntaxError as e:
        logging.error(f"❌ Syntax error in {filename}: {e}")
        return False
    except Exception as e:
        logging.error(f"❌ Error reading {filename}: {e}")
        return False

def fix_missing_files():
    """Check for missing files mentioned in the code and create them if necessary."""
    missing_files = []
    for root, _, files in os.walk("."):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    for line in lines:
                        if "open(" in line or "os.path.exists(" in line:
                            parts = line.split('"')
                            if len(parts) > 1:
                                file_path = parts[1]
                                if file_path and not os.path.exists(file_path):
                                    missing_files.append(file_path)
                                    with open(file_path, "w") as f:
                                        f.write("")  # Create an empty file
                                    logging.info(f"📂 Created missing file: {file_path}")
                except Exception as e:
                    logging.error(f"❌ Error while checking {filepath}: {e}")

def auto_fix_project():
    """Run all checks and fixes on all Python files in the project."""
    logging.info("🔍 Scanning project for issues...")

    all_files_valid = True  # Track if any syntax errors were found

    # Scan all Python files
    for root, _, files in os.walk("."):
        for file in files:
            if file.endswith(".py"):
                if not check_syntax(os.path.join(root, file)):
                    all_files_valid = False  # Found a syntax error

    fix_missing_files()

    print("✅ Auto-fix complete. Check fixer.log for details.")

    if all_files_valid:
        logging.info("🚀 Running bot.py...")
        print("🚀 Running bot.py...")
        subprocess.run(["python", "bot.py"])  # Run bot.py if no errors were found

# Run the fixer
if __name__ == "__main__":
    auto_fix_project()