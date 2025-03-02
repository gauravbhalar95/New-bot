import os
import time
import logging
from mega import Mega

class MegaNZHandler:
    def __init__(self):
        self.client = None

    def login(self, username=None, password=None):
        """Logs into Mega.nz using given credentials or anonymously."""
        try:
            mega = Mega()
            if username and password:
                self.client = mega.login(username, password)
                return "✅ Successfully logged in to Mega.nz!"
            else:
                self.client = mega.login()  # Anonymous login
                return "✅ Logged in to Mega.nz anonymously!"
        except Exception as e:
            return f"❌ Login failed: {str(e)}"

    def upload_to_mega(self, file_path, folder_name=None):
        """Uploads a file to Mega.nz and returns the public link."""
        if self.client is None:
            return None, "❌ Mega.nz is not logged in. Use /meganz <username> <password> to log in."

        if not os.path.exists(file_path):
            return None, "❌ File not found!"

        try:
            folder = None
            if folder_name:
                folder = self.client.find(folder_name)
                if folder:
                    folder = folder[0]

            uploaded_file = self.client.upload(file_path, folder) if folder else self.client.upload(file_path)
            link = self.client.get_upload_link(uploaded_file)
            return link, f"✅ File uploaded: {link}"
        except Exception as e:
            return None, f"❌ Upload Failed: {str(e)}"