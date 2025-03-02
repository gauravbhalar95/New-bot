import os
import aiohttp
import asyncio
from mega import Mega
from config import MEGA_USERNAME, MEGA_PASSWORD

class MegaNZ:
    def __init__(self):
        """Initialize MegaNZ client with optional login."""
        self.mega = Mega()
        self.client = None

    async def login(self, username, password):
        """Logs into Mega.nz asynchronously."""
        global MEGA_USERNAME, MEGA_PASSWORD
        try:
            self.client = await asyncio.to_thread(self.mega.login, username, password)
            MEGA_USERNAME, MEGA_PASSWORD = username, password
            return "✅ Login Successful!"
        except Exception as e:
            return f"❌ Login Failed: {str(e)}"

    async def download_from_url(self, url, folder_name="downloads"):
        """Asynchronously downloads a file from a URL."""
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        file_name = url.split("/")[-1]
        file_path = os.path.join(folder_name, file_name)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        with open(file_path, "wb") as file:
                            while chunk := await response.content.read(1024):
                                file.write(chunk)
            return file_path, f"✅ Downloaded: {file_name} to {folder_name}"
        except Exception as e:
            return None, f"❌ Download Failed: {str(e)}"

    async def upload_to_mega(self, file_path):
        """Uploads a file to Mega.nz asynchronously and returns the link."""
        if not self.client:
            return None, "❌ Please login first using /meganz <username> <password>"

        if not os.path.exists(file_path):
            return None, "❌ File not found!"

        try:
            # Upload file
            uploaded_file = await asyncio.to_thread(self.client.upload, file_path)
            # Get the file link
            link = await asyncio.to_thread(self.client.get_upload_link, uploaded_file)
            return link, f"✅ File uploaded: {link}"
        except Exception as e:
            return None, f"❌ Upload Failed: {str(e)}"