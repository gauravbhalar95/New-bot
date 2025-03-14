from quart import Quart, send_file
import os
from urllib.parse import quote
from quart import request

app = Quart(__name__)
DOWNLOAD_DIR = 'downloads'  # Ensure this matches your download directory path

@app.route('/download/<filename>')
async def download_file(filename):
    """Serves the requested file as a direct download link asynchronously."""
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if os.path.exists(file_path):
        return await send_file(file_path, as_attachment=True)
    return "❌ File not found", 404



def get_direct_download_link(file_path):
    """Generates a direct download link for the file using the Quart server's host and port."""
    file_name = quote(os.path.basename(file_path))
    server_url = request.host_url.rstrip('/')  # Dynamically fetches server's base URL
    return f"{server_url}/download/{file_name}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)