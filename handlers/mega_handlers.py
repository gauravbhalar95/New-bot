from mega import Mega

class MegaNZ:
    def __init__(self):
        self.mega = Mega()
        self.user = None

    async def login(self, email, password):
        try:
            self.user = self.mega.login(email, password)
            return "✅ **Mega.nz Login Successful!**"
        except Exception as e:
            return f"❌ **Mega.nz Login Failed:** {e}"

    async def download_from_url(self, url, folder):
        try:
            file_path = self.mega.download_url(url, folder)
            return file_path, f"✅ **Download completed:** `{file_path}`"
        except Exception as e:
            return None, f"❌ **Download Failed:** {e}"

    async def upload_to_mega(self, file_path):
        try:
            file = self.mega.upload(file_path)
            link = self.mega.get_upload_link(file)
            return link, f"✅ **Uploaded to Mega.nz:** [Download]({link})"
        except Exception as e:
            return None, f"❌ **Upload Failed:** {e}"