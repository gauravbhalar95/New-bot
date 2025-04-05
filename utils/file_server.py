from quart import Quart, send_file, request
import os
from urllib.parse import quote

app = Quart(__name__)
DOWNLOAD_DIR = 'downloads'  # Must exist and be writable

@app.route('/download/<filename>')
async def download_file(filename):
    """Serves the requested file as a direct download link asynchronously."""
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if os.path.isfile(file_path):
        return await send_file(file_path, as_attachment=True)
    return "❌ File not found", 404

def get_direct_download_link(file_path):
    """Generates a direct download link based on current request context."""
    file_name = quote(os.path.basename(file_path))
    base_url = request.host_url.rstrip('/') if request else "http://localhost:8080"
    return f"{base_url}/download/{file_name}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)