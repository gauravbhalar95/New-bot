import os
import time
import logging
import aiohttp

logger = logging.getLogger(__name__)

class DropboxTokenManager:
    def __init__(self):
        self.app_key = os.getenv("DROPBOX_APP_KEY")
        self.app_secret = os.getenv("DROPBOX_APP_SECRET")
        self.refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN")
        self.access_token = None
        self.expires_at = 0

    async def get_access_token(self):
        if not self.access_token or time.time() > self.expires_at:
            logger.info("Refreshing Dropbox access token...")
            await self.refresh_access_token()
        return self.access_token

    async def refresh_access_token(self):
        token_url = "https://api.dropbox.com/oauth2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.app_key,
            "client_secret": self.app_secret,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, data=data) as resp:
                if resp.status != 200:
                    logger.error(f"Dropbox token refresh failed: {resp.status}")
                    logger.error(await resp.text())
                    raise Exception("Failed to refresh Dropbox token")

                response = await resp.json()
                self.access_token = response["access_token"]
                expires_in = response.get("expires_in", 14400)
                self.expires_at = time.time() + expires_in - 60
                logger.info("Dropbox token refreshed successfully.")