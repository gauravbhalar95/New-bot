import os
import logging
import asyncio
import aiofiles
import aiohttp
from typing import Optional, Union

import dropbox
from dropbox.exceptions import AuthError, ApiError
from dropbox.files import WriteMode, UploadSessionCursor
from dropbox.sharing import SharedLinkSettings, RequestedVisibility

class AsyncDropboxUploader:
    """
    Asynchronous Dropbox file uploader with robust error handling.
    
    Supports:
    - Async large file uploads
    - Unique filename generation
    - Comprehensive error handling
    """
    
    def __init__(self, access_token: str, base_upload_path: str = "/telegram_uploads/", logger: Optional[logging.Logger] = None):
        """
        Initialize async Dropbox uploader.
        
        Args:
            access_token (str): Dropbox API access token
            base_upload_path (str, optional): Base directory for uploads
            logger (logging.Logger, optional): Logger instance
        """
        self.access_token = access_token
        self.base_upload_path = base_upload_path.rstrip('/')
        self.logger = logger or logging.getLogger(__name__)
    
    def _generate_unique_filename(self, chat_id: Union[str, int], original_filename: str) -> str:
        """
        Generate a unique filename to prevent conflicts.
        
        Args:
            chat_id (str/int): Unique identifier for the chat/user
            original_filename (str): Original filename
        
        Returns:
            str: Unique filename
        """
        import time
        timestamp = int(time.time())
        return f"{chat_id}_{timestamp}_{original_filename}"
    
    async def upload_file(self, file_path: str, chat_id: Optional[Union[str, int]] = None, chunk_size: int = 4*1024*1024) -> Optional[str]:
        """
        Asynchronously upload a file to Dropbox.
        
        Args:
            file_path (str): Path to the file to upload
            chat_id (str/int, optional): Chat/user ID for unique filename
            chunk_size (int, optional): Size of upload chunks
        
        Returns:
            Optional[str]: Shareable download link or None if upload fails
        """
        try:
            # Validate file existence
            if not os.path.exists(file_path):
                self.logger.error(f"File not found: {file_path}")
                return None
            
            # Generate filename
            filename = os.path.basename(file_path)
            if chat_id:
                filename = self._generate_unique_filename(chat_id, filename)
            
            dropbox_path = f"{self.base_upload_path}/{filename}"
            file_size = os.path.getsize(file_path)
            
            # Create Dropbox client
            async with aiohttp.ClientSession() as session:
                dbx = dropbox.Dropbox(self.access_token, session=session)
                
                # Validate authentication
                await asyncio.to_thread(dbx.users_get_current_account)
                
                # Large file upload strategy
                if file_size > 140 * 1024 * 1024:  # Over 140 MB
                    return await self._upload_large_file(dbx, file_path, dropbox_path, chunk_size)
                
                # Standard file upload
                return await self._upload_standard_file(dbx, file_path, dropbox_path)
        
        except Exception as e:
            self.logger.error(f"Unexpected upload error: {e}")
            return None
    
    async def _upload_standard_file(self, dbx: dropbox.Dropbox, file_path: str, dropbox_path: str) -> Optional[str]:
        """
        Upload smaller files asynchronously.
        
        Args:
            dbx (dropbox.Dropbox): Dropbox client
            file_path (str): Local file path
            dropbox_path (str): Dropbox destination path
        
        Returns:
            Optional[str]: Shareable download link
        """
        async with aiofiles.open(file_path, "rb") as f:
            file_contents = await f.read()
            
        # Upload file to Dropbox
        await asyncio.to_thread(
            dbx.files_upload, 
            file_contents, 
            dropbox_path, 
            mode=WriteMode.overwrite
        )
        
        return await self._create_shared_link(dbx, dropbox_path)
    
    async def _upload_large_file(self, dbx: dropbox.Dropbox, file_path: str, dropbox_path: str, chunk_size: int) -> Optional[str]:
        """
        Upload large files using async Dropbox upload session.
        
        Args:
            dbx (dropbox.Dropbox): Dropbox client
            file_path (str): Local file path
            dropbox_path (str): Dropbox destination path
            chunk_size (int): Size of upload chunks
        
        Returns:
            Optional[str]: Shareable download link
        """
        file_size = os.path.getsize(file_path)
        
        async with aiofiles.open(file_path, "rb") as f:
            # Start upload session with first chunk
            first_chunk = await f.read(chunk_size)
            upload_session = await asyncio.to_thread(
                dbx.files_upload_session_start, 
                first_chunk
            )
            
            # Prepare cursor
            cursor = UploadSessionCursor(
                session_id=upload_session.session_id, 
                offset=len(first_chunk)
            )
            
            # Upload remaining chunks
            while cursor.offset < file_size:
                # Read next chunk
                chunk = await f.read(chunk_size)
                
                if (file_size - cursor.offset) <= chunk_size:
                    # Final chunk
                    await asyncio.to_thread(
                        dbx.files_upload_session_finish,
                        chunk, 
                        cursor, 
                        dropbox.files.CommitInfo(path=dropbox_path)
                    )
                    break
                else:
                    # Intermediate chunks
                    await asyncio.to_thread(
                        dbx.files_upload_session_append_v2,
                        chunk, 
                        cursor
                    )
                    cursor.offset += len(chunk)
        
        return await self._create_shared_link(dbx, dropbox_path)
    
    async def _create_shared_link(self, dbx: dropbox.Dropbox, dropbox_path: str) -> Optional[str]:
        """
        Create a public shared link for the uploaded file.
        
        Args:
            dbx (dropbox.Dropbox): Dropbox client
            dropbox_path (str): Dropbox file path
        
        Returns:
            Optional[str]: Shareable download link
        """
        try:
            # Create shared link
            shared_link = await asyncio.to_thread(
                dbx.sharing_create_shared_link_with_settings,
                dropbox_path,
                SharedLinkSettings(
                    requested_visibility=RequestedVisibility.public
                )
            )
            
            # Convert to direct download link
            return shared_link.url.replace('dl=0', 'dl=1')
        
        except ApiError as e:
            # Handle existing shared link
            if e.error.is_path() and e.error.get_path().is_shared_link_already_exists():
                try:
                    links = await asyncio.to_thread(
                        dbx.sharing_list_shared_links, 
                        path=dropbox_path
                    )
                    if links.links:
                        return links.links[0].url.replace('dl=0', 'dl=1')
                except Exception as link_error:
                    self.logger.error(f"Error retrieving existing link: {link_error}")
            
            self.logger.error(f"Failed to create shared link: {e}")
            return None

# Example usage in async context
async def upload_to_dropbox(file_path: str, chat_id: Optional[Union[str, int]] = None) -> Optional[str]:
    """
    Async wrapper for Dropbox upload.
    
    Args:
        file_path (str): Path to the file to upload
        chat_id (str/int, optional): Chat/user ID for unique filename
    
    Returns:
        Optional[str]: Shareable download link
    """
    try:
        uploader = AsyncDropboxUploader(DROPBOX_ACCESS_TOKEN)
        return await uploader.upload_file(file_path, chat_id)
    except Exception as e:
        logger.error(f"Async Dropbox upload error: {e}")
        return None