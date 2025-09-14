# utils/mega_auth.py
import logging
import os
import json
from mega import Mega

logger = logging.getLogger(__name__)

class MegaTokenManager:
    """Manages authentication for MegaNZ API with persistent session"""

    def __init__(self, credentials_file="mega_credentials.json"):
        self.credentials_file = credentials_file
        self.email = os.environ.get('MEGA_EMAIL')
        self.password = os.environ.get('MEGA_PASSWORD')
        self.mega_instance = None

    async def get_access_token(self):
        """Always returns a valid MegaNZ session (lifetime login)."""
        if self.mega_instance is None:
            logger.info("MegaNZ session not initialized. Authenticating...")
            self.mega_instance = await self._authenticate()

        return self.mega_instance

    async def _authenticate(self):
        """Authenticates with MegaNZ and returns a persistent session."""
        try:
            mega = Mega()

            # Load credentials from file if available
            if os.path.exists(self.credentials_file):
                with open(self.credentials_file, 'r') as f:
                    credentials = json.load(f)
                    self.email = credentials.get('email', self.email)
                    self.password = credentials.get('password', self.password)

            # Check if we have credentials
            if not self.email or not self.password:
                logger.error("MegaNZ credentials not found (set MEGA_EMAIL and MEGA_PASSWORD)")
                return None

            # Login to Mega (persistent session)
            mega_instance = mega.login(self.email, self.password)

            # Save credentials (optional for backup)
            with open(self.credentials_file, 'w') as f:
                json.dump({"email": self.email, "password": self.password}, f)

            logger.info("✅ Successfully authenticated with MegaNZ (persistent session)")
            return mega_instance

        except Exception as e:
            logger.error(f"❌ Error authenticating with MegaNZ: {e}")
            return None