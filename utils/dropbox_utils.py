import os
import logging
import dropbox
from dropbox.exceptions import AuthError, ApiError
from dropbox.files import WriteMode, UploadSessionCursor
from dropbox.sharing import SharedLinkSettings, RequestedVisibility

class DropboxUploader:
    """
    A robust class for handling Dropbox file uploads with advanced features.
    
    Supports:
    - Large file uploads via session
    - Automatic file path generation
    - Configurable upload settings
    - Comprehensive error handling
    """
    
    def __init__(self, access_token, base_upload_path="/telegram_uploads/", logger=None):
        """
        Initialize Dropbox uploader with access token and configuration.
        
        Args:
            access_token (str): Dropbox API access token
            base_upload_path (str, optional): Base directory for uploads. Defaults to "/telegram_uploads/".
            logger (logging.Logger, optional): Logger instance. Creates a default if not provided.
        """
        try:
            self.dbx = dropbox.Dropbox(access_token)
            self.base_upload_path = base_upload_path
            
            # Validate access token immediately
            self.dbx.users_get_current_account()
            
            # Setup logging
            self.logger = logger or logging.getLogger(__name__)
        except Exception as e:
            raise AuthError(f"Dropbox authentication failed: {e}")
    
    def _generate_unique_filename(self, chat_id, original_filename):
        """
        Generate a unique filename to prevent conflicts.
        
        Args:
            chat_id (str/int): Unique identifier for the chat/user
            original_filename (str): Original filename
        
        Returns:
            str: Unique filename with timestamp and chat ID
        """
        import time
        timestamp = int(time.time())
        return f"{chat_id}_{timestamp}_{original_filename}"
    
    def upload_file(self, file_path, chat_id=None, chunk_size=4*1024*1024):
        """
        Upload a file to Dropbox with advanced handling for large files.
        
        Args:
            file_path (str): Path to the file to upload
            chat_id (str/int, optional): Chat/user ID for unique filename generation
            chunk_size (int, optional): Size of upload chunks. Defaults to 4MB.
        
        Returns:
            str: Shareable download link for the uploaded file, or None if upload fails
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
            
            dropbox_path = os.path.join(self.base_upload_path.rstrip('/'), filename).replace('\\', '/')
            file_size = os.path.getsize(file_path)
            
            # Large file upload strategy
            if file_size > 140 * 1024 * 1024:  # Over 140 MB
                return self._upload_large_file(file_path, dropbox_path, chunk_size)
            
            # Standard file upload
            return self._upload_standard_file(file_path, dropbox_path)
        
        except Exception as e:
            self.logger.error(f"Unexpected upload error: {e}")
            return None
    
    def _upload_standard_file(self, file_path, dropbox_path):
        """
        Upload smaller files in a single request.
        
        Args:
            file_path (str): Local file path
            dropbox_path (str): Dropbox destination path
        
        Returns:
            str: Shareable download link
        """
        with open(file_path, "rb") as f:
            self.dbx.files_upload(f.read(), dropbox_path, mode=WriteMode.overwrite)
        
        return self._create_shared_link(dropbox_path)
    
    def _upload_large_file(self, file_path, dropbox_path, chunk_size):
        """
        Upload large files using Dropbox upload session.
        
        Args:
            file_path (str): Local file path
            dropbox_path (str): Dropbox destination path
            chunk_size (int): Size of upload chunks
        
        Returns:
            str: Shareable download link
        """
        with open(file_path, "rb") as f:
            # Start upload session
            upload_session = self.dbx.files_upload_session_start(f.read(chunk_size))
            cursor = UploadSessionCursor(
                session_id=upload_session.session_id, 
                offset=f.tell()
            )
            
            # Upload remaining chunks
            while f.tell() < os.path.getsize(file_path):
                if (os.path.getsize(file_path) - f.tell()) <= chunk_size:
                    # Final chunk
                    self.dbx.files_upload_session_finish(
                        f.read(chunk_size), 
                        cursor, 
                        dropbox.files.CommitInfo(path=dropbox_path)
                    )
                    break
                else:
                    # Intermediate chunks
                    self.dbx.files_upload_session_append_v2(
                        f.read(chunk_size), 
                        cursor
                    )
                    cursor.offset = f.tell()
        
        return self._create_shared_link(dropbox_path)
    
    def _create_shared_link(self, dropbox_path):
        """
        Create a public shared link for the uploaded file.
        
        Args:
            dropbox_path (str): Dropbox file path
        
        Returns:
            str: Shareable download link
        """
        try:
            shared_link = self.dbx.sharing_create_shared_link_with_settings(
                dropbox_path,
                SharedLinkSettings(
                    requested_visibility=RequestedVisibility.public
                )
            )
            # Convert to direct download link
            return shared_link.url.replace('dl=0', 'dl=1')
        except ApiError as e:
            # If link already exists, retrieve existing link
            if e.error.is_path() and e.error.get_path().is_shared_link_already_exists():
                links = self.dbx.sharing_list_shared_links(path=dropbox_path).links
                if links:
                    return links[0].url.replace('dl=0', 'dl=1')
            
            self.logger.error(f"Failed to create shared link: {e}")
            return None