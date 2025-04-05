from quart import Quart, send_file, request
from urllib.parse import quote
import os

app = Quart(__name__)
DOWNLOAD_DIR = 'downloads'  # Make sure this directory exists
BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")  # Set this when deploying (e.g. on Koyeb)

@app.route('/download/<filename>')
async def download_file(filename):
    """Serves the requested file as a direct download link asynchronously."""
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if os.path.exists(file_path):
        return await send_file(file_path, as_attachment=True)
    return "❌ File not found", 404

def get_direct_download_link(file_path):
    """Generates a direct download link for a local file path."""
    if not os.path.exists(file_path):
        from utils.logger import logger
        logger.warning(f"File path does not exist: {file_path}")
        return None

    filename = quote(os.path.basename(file_path))
    return f"{BASE_URL}/download/{filename}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)