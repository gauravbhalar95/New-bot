# utils/dropbox_utils.py

from utils.dropbox_auth import DropboxTokenManager
import aiohttp

token_manager = DropboxTokenManager()

async def upload_to_dropbox(file_path, dropbox_dest):
    access_token = await token_manager.get_access_token()

    async with aiohttp.ClientSession() as session:
        with open(file_path, "rb") as f:
            data = f.read()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Dropbox-API-Arg": f'{{"path": "/{dropbox_dest}","mode": "add","autorename": true,"mute": false}}',
            "Content-Type": "application/octet-stream",
        }

        async with session.post("https://content.dropboxapi.com/2/files/upload", headers=headers, data=data) as response:
            if response.status == 200:
                return await get_shared_link(dropbox_dest, access_token)
            else:
                return None

async def get_shared_link(dropbox_dest, access_token):
    async with aiohttp.ClientSession() as session:
        data = {
            "path": f"/{dropbox_dest}",
            "settings": {"requested_visibility": "public"}
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        async with session.post("https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings", json=data, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                return result["url"].replace("?dl=0", "?dl=1")
            else:
                return None