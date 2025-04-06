import os
import gc
import logging
import asyncio
import aiofiles
import re
import dropbox
from dropbox.exceptions import AuthError, ApiError
from telebot.async_telebot import AsyncTeleBot

# Import local modules
from config import (
    API_TOKEN,
    TELEGRAM_FILE_LIMIT,
    DROPBOX_ACCESS_TOKEN,
    MAX_WORKERS,  # Add this to config.py (default: 3)
    MAX_RETRIES,  # Add this to config.py (default: 3)
    CHUNK_SIZE,   # Add this to config.py (default: 4*1024*1024 - 4MB)
)
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from utils.image_handlers import process_instagram_image
from handlers.facebook_handlers import process_facebook  
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import process_video_trim, process_audio_trim
from utils.logger import setup_logging

# Constants
MAX_FILE_SIZE = 140 * 1024 * 1024  # 140MB - Dropbox chunked upload threshold
TELEGRAM_SAFE_LIMIT = 49 * 1024 * 1024  # 49MB - Safe limit for Telegram uploads

# Logging setup with enhanced formatting
logger = setup_logging(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class MediaDownloadBot:
    def __init__(self):
        """Initialize the MediaDownloadBot with necessary configurations."""
        self.bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
        self.download_queue = asyncio.Queue()
        self.dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
        
        # Platform patterns with improved regex
        self.PLATFORM_PATTERNS = {
            "YouTube": re.compile(r"(?:youtube\.com/\S*(?:(?:/e(?:mbed)?)?/|watch\?(?:\S*?&?v=))|youtu\.be/)[a-zA-Z0-9_-]+"),
            "Instagram": re.compile(r"(?:instagram\.com(?:/[^/]+)?/(?:p|reel|tv)/[^/?#&]+)"),
            "Facebook": re.compile(r"(?:facebook\.com|fb\.watch)/(?:(?:\w+)/)?(?:videos|watch|story)(?:/[^/?#&]+)?"),
            "Twitter/X": re.compile(r"(?:twitter\.com|x\.com)/\w+/status/\d+"),
            "Adult": re.compile(r"(?:pornhub\.com|xvideos\.com|redtube\.com|xhamster\.com|xnxx\.com)/\S+"),
        }
        
        # Platform handlers mapping
        self.PLATFORM_HANDLERS = {
            "YouTube": process_youtube,
            "Instagram": process_instagram,
            "Facebook": process_facebook,
            "Twitter/X": download_twitter_media,
            "Adult": process_adult,
        }

        # Register message handlers
        self._register_handlers()

    def _register_handlers(self):
        """Register all message handlers for the bot."""
        self.bot.message_handler(commands=["start", "help"])(self.send_welcome)
        self.bot.message_handler(commands=["audio"])(self.handle_audio_request)
        self.bot.message_handler(commands=["image"])(self.handle_image_request)
        self.bot.message_handler(commands=["trim"])(self.handle_video_trim_request)
        self.bot.message_handler(commands=["trimAudio"])(self.handle_audio_trim_request)
        self.bot.message_handler(func=lambda msg: True, content_types=["text"])(self.handle_message)

    async def send_message(self, chat_id, text, parse_mode="HTML", retry_count=0):
        """Send a message with retry logic."""
        try:
            await self.bot.send_message(chat_id, text, parse_mode=parse_mode)
        except Exception as e:
            if retry_count < MAX_RETRIES:
                logger.warning(f"Retrying message send. Attempt {retry_count + 1}")
                await asyncio.sleep(1)
                await self.send_message(chat_id, text, parse_mode, retry_count + 1)
            else:
                logger.error(f"Failed to send message after {MAX_RETRIES} attempts: {e}")

    def detect_platform(self, url):
        """Detect platform from URL using regex patterns."""
        for platform, pattern in self.PLATFORM_PATTERNS.items():
            if pattern.search(url):
                return platform
        return None

    async def upload_to_dropbox(self, file_path, filename):
        """Upload file to Dropbox with chunked upload support."""
        try:
            # Validate Dropbox token
            try:
                self.dbx.users_get_current_account()
            except Exception as auth_error:
                logger.error(f"Dropbox authentication failed: {auth_error}")
                return None

            dropbox_path = f"/telegram_uploads/{filename}"
            
            async with aiofiles.open(file_path, "rb") as f:
                file_size = os.path.getsize(file_path)

                if file_size > MAX_FILE_SIZE:
                    # Chunked upload for large files
                    upload_session = self.dbx.files_upload_session_start(await f.read(CHUNK_SIZE))
                    cursor = dropbox.files.UploadSessionCursor(
                        session_id=upload_session.session_id,
                        offset=CHUNK_SIZE
                    )

                    while cursor.offset < file_size:
                        chunk = await f.read(CHUNK_SIZE)
                        if len(chunk) == 0:
                            break
                            
                        if (file_size - cursor.offset) <= CHUNK_SIZE:
                            self.dbx.files_upload_session_finish(
                                chunk,
                                cursor,
                                dropbox.files.CommitInfo(path=dropbox_path)
                            )
                        else:
                            self.dbx.files_upload_session_append_v2(chunk, cursor)
                            cursor.offset += len(chunk)
                else:
                    # Regular upload for smaller files
                    file_content = await f.read()
                    self.dbx.files_upload(file_content, dropbox_path, mode=dropbox.files.WriteMode.overwrite)

            # Create shared link
            shared_link = self.dbx.sharing_create_shared_link_with_settings(
                dropbox_path,
                dropbox.sharing.SharedLinkSettings(
                    requested_visibility=dropbox.sharing.RequestedVisibility.public
                )
            )
            return shared_link.url.replace('dl=0', 'dl=1')

        except (AuthError, ApiError) as e:
            logger.error(f"Dropbox API error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during Dropbox upload: {str(e)}")
            return None

    # The rest of your handler methods (process_download, process_image_download, etc.) 
    # would go here with similar improvements in error handling and organization

    async def start_workers(self):
        """Start worker tasks for processing downloads."""
        num_workers = min(MAX_WORKERS, os.cpu_count() or 1)
        workers = [asyncio.create_task(self.worker()) for _ in range(num_workers)]
        return workers

    async def run(self):
        """Run the bot with proper error handling."""
        try:
            workers = await self.start_workers()
            logger.info(f"Started {len(workers)} worker tasks")
            
            await self.bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"Bot runtime error: {e}", exc_info=True)
            # Cancel worker tasks
            for worker in workers:
                worker.cancel()
        finally:
            # Wait for workers to complete
            for worker in workers:
                try:
                    await worker
                except asyncio.CancelledError:
                    pass

def main():
    """Main entry point for the bot."""
    bot = MediaDownloadBot()
    asyncio.run(bot.run())

if __name__ == "__main__":
    main()