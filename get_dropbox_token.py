#!/usr/bin/env python3
import os
import json
import logging
from datetime import datetime
from dropbox import DropboxOAuth2FlowNoRedirect
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dropbox_setup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DropboxTokenSetup:
    def __init__(self):
        self.config_dir = Path.home() / '.config' / 'telegram_bot'
        self.tokens_file = self.config_dir / 'dropbox_tokens.json'
        self.create_config_dir()

    def create_config_dir(self):
        """Create configuration directory if it doesn't exist."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Configuration directory ready: {self.config_dir}")
        except Exception as e:
            logger.error(f"Failed to create config directory: {e}")
            raise

    def save_tokens(self, token_data):
        """Save token data to JSON file."""
        try:
            token_data['generated_at'] = datetime.utcnow().isoformat()
            token_data['generated_by'] = os.getenv('USER', 'unknown')
            
            with open(self.tokens_file, 'w', encoding='utf-8') as f:
                json.dump(token_data, f, indent=4)
            
            # Set secure permissions
            os.chmod(self.tokens_file, 0o600)
            logger.info(f"Tokens saved securely to: {self.tokens_file}")
            
        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")
            raise

    def load_tokens(self):
        """Load existing tokens if available."""
        try:
            if self.tokens_file.exists():
                with open(self.tokens_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info("Existing tokens found")
                return data
        except Exception as e:
            logger.error(f"Error loading existing tokens: {e}")
        return None

    def generate_tokens(self):
        """Generate new Dropbox OAuth tokens."""
        try:
            print("\n=== Dropbox Token Generator ===")
            print("This script will help you set up Dropbox OAuth tokens for your bot.")
            
            # Check for existing tokens
            existing_tokens = self.load_tokens()
            if existing_tokens:
                print("\nExisting tokens found. Options:")
                print("1. Use existing tokens")
                print("2. Generate new tokens")
                choice = input("\nYour choice (1/2): ").strip()
                if choice == "1":
                    return existing_tokens

            # Get app credentials
            print("\nPlease enter your Dropbox API credentials:")
            app_key = input("App Key: ").strip()
            app_secret = input("App Secret: ").strip()

            # Initialize OAuth flow
            auth_flow = DropboxOAuth2FlowNoRedirect(app_key, app_secret)
            authorize_url = auth_flow.start()

            # Display instructions
            print("\nFollow these steps to complete the setup:")
            print("-" * 50)
            print("1. Visit this URL in your browser:", authorize_url)
            print("2. Click 'Allow' (you may need to log in first)")
            print("3. Copy the authorization code")
            print("-" * 50)

            # Get authorization code
            auth_code = input("\nEnter the authorization code: ").strip()

            # Complete OAuth flow
            try:
                oauth_result = auth_flow.finish(auth_code)
                
                # Prepare token data
                token_data = {
                    "app_key": app_key,
                    "app_secret": app_secret,
                    "access_token": oauth_result.access_token,
                    "refresh_token": oauth_result.refresh_token,
                    "expires_in": oauth_result.expires_in,
                    "account_id": oauth_result.account_id
                }

                # Save tokens
                self.save_tokens(token_data)

                print("\n✅ Setup completed successfully!")
                print(f"Tokens have been saved to: {self.tokens_file}")
                print("\nToken Details:")
                print(f"- Access Token: {oauth_result.access_token[:10]}...")
                print(f"- Refresh Token: {oauth_result.refresh_token[:10]}...")
                print(f"- Expires In: {oauth_result.expires_in} seconds")
                
                return token_data

            except Exception as e:
                logger.error(f"OAuth flow failed: {e}")
                print("\n❌ Error completing OAuth flow. Please try again.")
                return None

        except Exception as e:
            logger.error(f"Token generation failed: {e}")
            print("\n❌ An error occurred during setup.")
            return None

def main():
    """Main entry point for token setup."""
    try:
        setup = DropboxTokenSetup()
        tokens = setup.generate_tokens()
        
        if tokens:
            print("\nSetup completed successfully! You can now use these tokens in your bot.")
            print("Make sure to update your config.py with the new credentials.")
        else:
            print("\nSetup failed. Please check the logs and try again.")
            
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print("\nAn unexpected error occurred. Please check the logs.")

if __name__ == "__main__":
    main()