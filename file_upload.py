import os
import logging
from mega import Mega
from asyncio import to_thread
from config import MEGA_EMAIL, MEGA_PASSWORD

logger = logging.getLogger(__name__)

async def upload_to_mega(file_path, filename):
    """Uploads file to MegaNZ and returns a download link."""
    try:
        # Run the Mega operations in a thread pool since the Mega API is synchronous
        def mega_upload_operation():
            # Initialize Mega instance
            mega = Mega()
            
            # Login to Mega
            m = mega.login(MEGA_EMAIL, MEGA_PASSWORD)
            
            # Create folder if it doesn't exist
            folder_name = 'telegram_uploads'
            folders = m.get_folders()
            
            # Check if the folder exists, if not create it
            folder_id = None
            for f in folders:
                if folders[f]['a']['n'] == folder_name:
                    folder_id = f
                    break
            
            if folder_id is None:
                folder_id = m.create_folder(folder_name)
            
            # Upload file to the folder
            file_details = m.upload(file_path, folder_id)
            
            # Generate a download link
            link = m.get_upload_link(file_details)
            return link
        
        # Run the synchronous Mega operation in a thread pool
        link = await to_thread(mega_upload_operation)
        
        if link:
            logger.info(f"Successfully uploaded to MegaNZ: {link}")
            return link
        else:
            logger.error("Failed to get MegaNZ download link")
            return None
            
    except Exception as e:
        logger.error(f"Error uploading to MegaNZ: {e}")
        return None