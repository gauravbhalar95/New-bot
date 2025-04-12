# utils/mega_auth.py
import logging
import os
import json
from mega import Mega
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MegaTokenManager:
    """Manages authentication for MegaNZ API"""
    
    def __init__(self, credentials_file="mega_credentials.json"):
        self.credentials_file = credentials_file
        self.email = os.environ.get('MEGA_EMAIL')
        self.password = os.environ.get('MEGA_PASSWORD')
        self.session_expiry = None
        self.mega_instance = None
        
    async def get_access_token(self):
        """Returns a valid MegaNZ session or authenticates if needed."""
        now = datetime.now()
        
        # Check if we need to authenticate
        if self.mega_instance is None or (self.session_expiry and now >= self.session_expiry):
            logger.info("MegaNZ session expired or not initialized. Authenticating...")
            self.mega_instance = await self._authenticate()
            
            # Set the session expiry to 1 hour from now
            # Most APIs have some expiry time
            self.session_expiry = now + timedelta(hours=1)
            
        return self.mega_instance
    
    async def _authenticate(self):
        """Authenticates with MegaNZ and returns a session."""
        try:
            # Initialize Mega
            mega = Mega()
            
            # Load credentials from file if available
            if os.path.exists(self.credentials_file):
                with open(self.credentials_file, 'r') as f:
                    credentials = json.load(f)
                    self.email = credentials.get('email', self.email)
                    self.password = credentials.get('password', self.password)
            
            # Check if we have credentials
            if not self.email or not self.password:
                logger.error("MegaNZ credentials not found")
                return None
                
            # Login to Mega
            # Note: This isn't truly async, but we're treating it as such
            # for compatibility with the rest of the code
            mega_instance = mega.login(self.email, self.password)
            
            logger.info("Successfully authenticated with MegaNZ")
            return mega_instance
            
        except Exception as e:
            logger.error(f"Error authenticating with MegaNZ: {e}")
            return None
