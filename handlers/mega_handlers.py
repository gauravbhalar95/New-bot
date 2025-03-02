import os
import requests
from mega import Mega
from config import MEGA_USERNAME, MEGA_PASSWORD

class MegaNZ:
    def __init__(self):
        self.mega = Mega()
        self.client = None
        if MEGA_USERNAME and MEGA_PASSWORD:
            self.login(MEGA_USERNAME, MEGA_PASSWORD)

    def login(self, username, password):
        """Logs into Mega.nz and saves credentials."""
        global MEGA_USERNAME, MEGA_PASSWORD
        try:
            self.client = self.mega.login(username, password)
            MEGA_USERNAME, MEGA_PASSWORD = username, password
            return "✅ Login Successful!"
        except Exception as e:
            return f"❌ Login Failed: {str(e)}"

    def download_from_url(self, url, folder_name="downloads"):
        """Downloads a file from any URL to a specific folder."""
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        file_name = url.split("/")[-1]
        file_path = os.path.join(folder_name, file_name)

        try:
            response = requests.get(url, stream=True)
            with open(file_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)

            return file_path, f"✅ Downloaded: {file_name} to {folder_name}"
        except Exception as e:
            return None, f"❌ Download Failed: {str(e)}"

    def upload_to_mega(self, file_path):
        """Uploads a file to Mega.nz and returns the public link."""
        if not self.client:
            return None, "❌ Please login first using /meganz <username> <password>"

        if not os.path.exists(file_path):
            return None, "❌ File not found!"

        try:
            uploaded_file = self.client.upload(file_path)
            link = self.client.get_upload_link(uploaded_file)
            return link, f"✅ File uploaded: {link}"
        except Exception as e:
            return None, f"❌ Upload Failed: {str(e)}"