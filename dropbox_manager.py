import time
import logging
from dropbox import Dropbox, DropboxOAuth2FlowNoRedirect, DropboxOAuth2Flow
from dropbox.oauth import OAuth2AccessToken, OAuth2FlowNoRedirectResult
from dropbox.exceptions import AuthError
from config import (
    DROPBOX_APP_KEY,
    DROPBOX_APP_SECRET,
    DROPBOX_REFRESH_TOKEN
)

logger = logging.getLogger(__name__)

class DropboxTokenManager:
    def __init__(self, app_key, app_secret, refresh_token):
        self.app_key = app_key
        self.app_secret = app_secret
        self.refresh_token = refresh_token
        self.access_token = None
        self.token_expiry = 0
        self.dbx = None

    async def get_client(self):
        """Return a valid Dropbox client, refresh token if needed."""
        current_time = time.time()
        if not self.dbx or current_time + 300 >= self.token_expiry:
            await self.refresh_access_token()
        return self.dbx

    async def refresh_access_token(self):
        """Refresh access token using the long-term refresh token."""
        try:
            logger.info("Refreshing Dropbox access token...")

            self.dbx = Dropbox(
                oauth2_refresh_token=self.refresh_token,
                app_key=self.app_key,
                app_secret=self.app_secret
            )

            # Force a call to verify token and fetch metadata (forces refresh)
            account_info = self.dbx.users_get_current_account()
            self.token_expiry = time.time() + 14400  # Dropbox tokens last ~4 hours
            logger.info("Dropbox token refreshed. Account: %s", account_info.email)

        except AuthError as e:
            logger.error(f"Dropbox authentication failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while refreshing token: {e}")
            raise