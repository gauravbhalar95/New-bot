import ast
import os
import logging
import asyncio
import aiofiles
import subprocess

# Logging setup
logging.basicConfig(
    filename="fixer.log", 
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s"
)

async def check_syntax(filename):
    """Asynchronously check if the Python file has syntax errors."""
    try:
        async with aiofiles.open(filename, "r", encoding="utf-8") as f:
            source = await f.read()
        ast.parse(source)  # Parse the source code
        logging.info(f"✅ No syntax errors found in {filename}")
        return True
    except SyntaxError as e:
        logging.error(f"❌ Syntax error in {filename}: {e}")
        return False
    except Exception as e:
        logging.error(f"❌ Error reading {filename}: {e}")
        return False

async def check_static_errors(filename):
    """Asynchronously check for function call errors using pylint."""
    try:
        process = await asyncio.create_subprocess_exec(
            "pylint", "--disable=all", "--enable=E1120", filename,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logging.error(f"❌ Static error in {filename}:\n{stdout.decode()}")
        else:
            logging.info(f"✅ No function call errors in {filename}")
    except Exception as e:
        logging.error(f"❌ Error running static analysis on {filename}: {e}")

async def fix_missing_files():
    """Asynchronously check for missing files mentioned in the code and create them if necessary."""
    missing_files = set()
    
    for root, _, files in os.walk("."):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                try:
                    async with aiofiles.open(filepath, "r", encoding="utf-8") as f:
                        lines = await f.readlines()
                    
                    for line in lines:
                        if "open(" in line or "os.path.exists(" in line:
                            parts = line.split('"')
                            if len(parts) > 1:
                                file_path = parts[1]
                                if file_path and not os.path.exists(file_path):
                                    missing_files.add(file_path)
                                    async with aiofiles.open(file_path, "w") as f:
                                        await f.write("")  # Create an empty file
                                    logging.info(f"📂 Created missing file: {file_path}")
                except Exception as e:
                    logging.error(f"❌ Error while checking {filepath}: {e}")

async def auto_fix_project():
    """Run all checks and fixes on all Python files asynchronously."""
    logging.info("🔍 Scanning project for issues...")

    tasks = []
    for root, _, files in os.walk("."):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                tasks.append(check_syntax(filepath))
                tasks.append(check_static_errors(filepath))

    await asyncio.gather(*tasks)  # Run all checks in parallel

    await fix_missing_files()  # Fix missing files

    print("✅ Auto-fix complete. Check fixer.log for details.")

    # Run bot.py automatically if it exists
    if os.path.exists("bot.py"):
        logging.info("🚀 Running bot.py...")
        process = await asyncio.create_subprocess_exec("python", "bot.py")
        await process.wait()  # Wait for bot to start

# Run the fixer
if __name__ == "__main__":
    asyncio.run(auto_fix_project())