import asyncio
from mega import Mega

class MegaNZ:
    def __init__(self):
        self.mega = Mega()
        self.user = None

    async def login(self, email, password):
        """Login to Mega.nz"""
        try:
            self.user = await asyncio.to_thread(self.mega.login, email, password)
            return "✅ **Mega.nz Login Successful!**"
        except Exception as e:
            return f"❌ **Mega.nz Login Failed:** {e}"

    async def download_from_url(self, url, folder):
        """Download file from Mega.nz public URL"""
        try:
            file_path = await asyncio.to_thread(self.mega.download_url, url, folder)
            return file_path, f"✅ **Download completed:** `{file_path}`"
        except Exception as e:
            return None, f"❌ **Download Failed:** {e}"

    async def upload_to_mega(self, file_path):
        """Upload file to Mega.nz and return share link"""
        try:
            file = await asyncio.to_thread(self.mega.upload, file_path)
            link = await asyncio.to_thread(self.mega.get_link, file)
            return link, f"✅ **Uploaded to Mega.nz:** [Download Link]({link})"
        except Exception as e:
            return None, f"❌ **Upload Failed:** {e}"