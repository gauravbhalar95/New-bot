import time
from dropbox import Dropbox
from dropbox.oauth import DropboxOAuth2FlowNoRedirect
import logging

logger = logging.getLogger(__name__)

class DropboxTokenManager:
    def __init__(self, app_key, app_secret, refresh_token=None):
        self.app_key = app_key
        self.app_secret = app_secret
        self.refresh_token = refresh_token
        self.access_token = None
        self.token_expiry = 0
        self.dbx = None

    async def get_client(self):
        """Returns a valid Dropbox client, refreshing the token if necessary."""
        current_time = time.time()
        
        # If token is expired or will expire in next 5 minutes
        if not self.access_token or current_time + 300 >= self.token_expiry:
            await self.refresh_access_token()
            
        return self.dbx

    async def refresh_access_token(self):
        """Refreshes the access token using the refresh token."""
        try:
            auth_flow = DropboxOAuth2FlowNoRedirect(self.app_key, self.app_secret)
            
            if self.refresh_token:
                # Get a new access token using the refresh token
                oauth_result = auth_flow.finish({'refresh_token': self.refresh_token})
                self.access_token = oauth_result.access_token
                self.token_expiry = time.time() + oauth_result.expires_in
                self.dbx = Dropbox(self.access_token)
                logger.info("Successfully refreshed Dropbox access token")
            else:
                logger.error("No refresh token available")
                raise Exception("No refresh token available for Dropbox authentication")
                
        except Exception as e:
            logger.error(f"Error refreshing Dropbox token: {e}")
            raise