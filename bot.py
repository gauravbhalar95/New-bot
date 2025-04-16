import os
import gc
import logging
import asyncio
import aiofiles
import re
import dropbox
from dropbox.exceptions import AuthError, ApiError
from telebot.async_telebot import AsyncTeleBot
import json
import time
from datetime import datetime, timedelta
import signal
from aiohttp import web

# Import local modules
from config import API_TOKEN, TELEGRAM_FILE_LIMIT, DROPBOX_ACCESS_TOKEN, DROPBOX_REFRESH_TOKEN, DROPBOX_APP_KEY, DROPBOX_APP_SECRET
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import process_video_trim, process_audio_trim
from handlers.image_handlers import process_instagram_image
from utils.logger import setup_logging

# Logging setup
logger = setup_logging(logging.DEBUG)

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()

# Flag to track bot running state
bot_running = False
shutdown_event = asyncio.Event()

# Dropbox token management
class DropboxTokenManager:
    def __init__(self, access_token, refresh_token, app_key, app_secret):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.app_key = app_key
        self.app_secret = app_secret
        self.expiration_time = datetime.now() + timedelta(hours=3)  # Default expiration (tokens usually last 4 hours)
        self.token_file = "dropbox_token_data.json"
        self.load_token_data()
        
    def load_token_data(self):
        """Load token data from file if exists"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                    self.access_token = data.get('access_token', self.access_token)
                    self.refresh_token = data.get('refresh_token', self.refresh_token)
                    expiry_str = data.get('expiration_time')
                    if expiry_str:
                        self.expiration_time = datetime.fromisoformat(expiry_str)
                    logger.info("Loaded Dropbox token data from file")
        except Exception as e:
            logger.error(f"Error loading token data: {e}")
    
    def save_token_data(self):
        """Save token data to file"""
        try:
            data = {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'expiration_time': self.expiration_time.isoformat()
            }
            with open(self.token_file, 'w') as f:
                json.dump(data, f)
            logger.info("Saved Dropbox token data to file")
        except Exception as e:
            logger.error(f"Error saving token data: {e}")
    
    async def refresh_if_needed(self):
        """Check if token needs refreshing and refresh if necessary"""
        if datetime.now() >= self.expiration_time:
            await self.refresh_token_async()
            return True
        return False
    
    async def refresh_token_async(self):
        """Refresh the access token asynchronously"""
        logger.info("Refreshing Dropbox access token...")
        
        try:
            # Using the app key and app secret to get a new access token
            dbx = dropbox.Dropbox(
                app_key=self.app_key,
                app_secret=self.app_secret,
                oauth2_refresh_token=self.refresh_token
            )
            
            # This will automatically refresh the token
            dbx.users_get_current_account()
            
            # Get the new tokens
            self.access_token = dbx._oauth2_access_token
            self.refresh_token = dbx._oauth2_refresh_token
            
            # Set new expiration (usually 4 hours from now)
            self.expiration_time = datetime.now() + timedelta(hours=3)
            
            # Save the new token data
            self.save_token_data()
            
            logger.info("Successfully refreshed Dropbox access token")
            return True
            
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return False
    
    def get_client(self):
        """Get a Dropbox client with the current token"""
        return dropbox.Dropbox(self.access_token)

# Initialize token manager
token_manager = DropboxTokenManager(
    DROPBOX_ACCESS_TOKEN, 
    DROPBOX_REFRESH_TOKEN,
    DROPBOX_APP_KEY,
    DROPBOX_APP_SECRET
)

# Regex patterns for different platforms
PLATFORM_PATTERNS = {
    "YouTube": re.compile(r"(youtube\.com|youtu\.be)"),
    "Instagram": re.compile(r"instagram\.com"),
    "Facebook": re.compile(r"facebook\.com"),
    "Twitter/X": re.compile(r"(x\.com|twitter\.com)"),
    "Adult": re.compile(r"(pornhub\.com|xvideos\.com|redtube\.com|xhamster\.com|xnxx\.com)"),
}

# Platform handlers
PLATFORM_HANDLERS = {
    "YouTube": process_youtube,
    "Instagram": process_instagram,
    "Facebook": process_facebook,
    "Twitter/X": download_twitter_media,
    "Adult": process_adult,
}

async def send_message(chat_id, text):
    """Sends a message asynchronously."""
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"Error sending message: {e}")


def detect_platform(url):
    """Detects the platform based on URL patterns."""
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None


async def upload_to_dropbox(file_path, filename):
    """
    Uploads a file to Dropbox and returns a shareable link.

    Args:
        file_path (str): Path to the file to upload
        filename (str): Name to use for the file in Dropbox

    Returns:
        str: Shareable link to the uploaded file
    """
    try:
        # Check if token needs refreshing
        await token_manager.refresh_if_needed()
        dbx = token_manager.get_client()
        
        # Validate access token
        try:
            dbx.users_get_current_account()
        except AuthError:
            logger.info("Access token validation failed, attempting refresh")
            if await token_manager.refresh_token_async():
                dbx = token_manager.get_client()
            else:
                logger.error("Token refresh failed")
                return None
        except Exception as auth_error:
            logger.error(f"Dropbox authentication failed: {auth_error}")
            return None

        dropbox_path = f"/telegram_uploads/{filename}"
        file_size = os.path.getsize(file_path)

        with open(file_path, "rb") as f:
            if file_size > 140 * 1024 * 1024:  # 140 MB threshold
                logger.info("Large file detected, using upload session")
                upload_session = dbx.files_upload_session_start(f.read(4 * 1024 * 1024))
                cursor = dropbox.files.UploadSessionCursor(
                    session_id=upload_session.session_id,
                    offset=f.tell()
                )

                while f.tell() < file_size:
                    chunk_size = 4 * 1024 * 1024
                    if (file_size - f.tell()) <= chunk_size:
                        dbx.files_upload_session_finish(
                            f.read(chunk_size),
                            cursor,
                            dropbox.files.CommitInfo(path=dropbox_path)
                        )
                        break
                    else:
                        dbx.files_upload_session_append_v2(
                            f.read(chunk_size),
                            cursor
                        )
                        cursor.offset = f.tell()
            else:
                dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)

        shared_link = dbx.sharing_create_shared_link_with_settings(
            dropbox_path,
            dropbox.sharing.SharedLinkSettings(
                requested_visibility=dropbox.sharing.RequestedVisibility.public
            )
        )
        return shared_link.url.replace('dl=0', 'dl=1')

    except AuthError as auth_error:
        logger.error(f"Dropbox authentication error: {auth_error}")
        # Try token refresh and retry once
        if await token_manager.refresh_token_async():
            return await upload_to_dropbox(file_path, filename)  # Retry after refresh
        return None
    except ApiError as api_error:
        logger.error(f"Dropbox API error: {api_error}")
        return None
    except Exception as e:
        logger.error(f"Unexpected Dropbox upload error: {e}")
        return None

async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    """Handles video/audio download and sends it to Telegram or Dropbox."""
    try:
        request_type = "Video Download"
        if is_audio:
            request_type = "Audio Download"
        elif is_video_trim:
            request_type = "Video Trimming"
        elif is_audio_trim:
            request_type = "Audio Trimming"

        await send_message(message.chat.id, f"📥 **Processing your {request_type.lower()}...**")
        logger.info(f"Processing URL: {url}, Type: {request_type}")

        # Detect platform
        platform = detect_platform(url)
        if not platform:
            await send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        # Handle request based on type
        if is_video_trim:
            logger.info(f"Processing video trim request: Start={start_time}, End={end_time}")
            file_path, file_size = await process_video_trim(url, start_time, end_time)
            download_url = None
            file_paths = [file_path] if file_path else []

        elif is_audio_trim:
            logger.info(f"Processing audio trim request: Start={start_time}, End={end_time}")
            file_path, file_size = await process_audio_trim(url, start_time, end_time)
            download_url = None
            file_paths = [file_path] if file_path else []

        elif is_audio:
            result = await extract_audio_ffmpeg(url)
            if isinstance(result, tuple):
                file_path, file_size = result if len(result) == 2 else (result[0], None)
                download_url = None
                file_paths = [file_path] if file_path else []
            else:
                file_path, file_size, download_url = result, None, None
                file_paths = [file_path] if file_path else []

        else:
            if platform == "Instagram":
                if "/reel/" in url or "/tv/" in url:
                    result = await process_instagram(url)  # Handles Reels and IGTV videos
                else:
                    result = await process_instagram_image(url)  # Handles posts and stories
            else:
                result = await PLATFORM_HANDLERS[platform](url)

            # Handle different return formats from platform handlers
            if isinstance(result, tuple) and len(result) >= 3:
                file_paths, file_size, download_url = result
                if not isinstance(file_paths, list):
                    file_paths = [file_paths] if file_paths else []
            elif isinstance(result, tuple) and len(result) == 2:
                file_paths, file_size = result
                download_url = None
                if not isinstance(file_paths, list):
                    file_paths = [file_paths] if file_paths else []
            else:
                file_paths = result if isinstance(result, list) else [result] if result else []
                file_size = None
                download_url = None

        logger.info(f"Platform handler returned: file_paths={file_paths}, file_size={file_size}, download_url={download_url}")

        if not file_paths or all(not path for path in file_paths):
            logger.warning("No valid file paths returned from platform handler")
            await send_message(message.chat.id, "❌ **Download failed. No media found.**")
            return

        for file_path in file_paths:
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"File path does not exist: {file_path}")
                continue

            if file_size is None:
                file_size = os.path.getsize(file_path)

            if file_size > TELEGRAM_FILE_LIMIT or file_size > 49 * 1024 * 1024:
                filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                logger.info(f"File too large for Telegram: {file_size} bytes. Using Dropbox.")
                dropbox_link = await upload_to_dropbox(file_path, filename)

                if dropbox_link:
                    logger.info(f"Successfully uploaded to Dropbox: {dropbox_link}")
                    await send_message(
                        message.chat.id,
                        f"⚠️ **File too large for Telegram.**\n📥 [Download from Dropbox]({dropbox_link})"
                    )
                else:
                    logger.warning("Dropbox upload failed")
                    if download_url:
                        await send_message(
                            message.chat.id,
                            f"⚠️ **File too large for Telegram.**\n📥 [Download here]({download_url})"
                        )
                    else:
                        await send_message(message.chat.id, "❌ **Download failed.**")
            else:
                try:
                    async with aiofiles.open(file_path, "rb") as file:
                        file_content = await file.read()
                        file_size_actual = len(file_content)

                        if file_size_actual > TELEGRAM_FILE_LIMIT:
                            logger.warning(f"Actual size exceeds limit: {file_size_actual}")
                            filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                            dropbox_link = await upload_to_dropbox(file_path, filename)

                            if dropbox_link:
                                await send_message(
                                    message.chat.id,
                                    f"⚠️ **File too large for Telegram.**\n📥 [Download from Dropbox]({dropbox_link})"
                                )
                            else:
                                await send_message(message.chat.id, "❌ **File too large. Upload failed.**")
                        else:
                            if is_audio or is_audio_trim:
                                await bot.send_audio(message.chat.id, file_content, timeout=600)
                            else:
                                await bot.send_video(message.chat.id, file_content, supports_streaming=True, timeout=600)

                except Exception as send_error:
                    logger.error(f"Error sending file to Telegram: {send_error}")
                    if "413" in str(send_error):
                        logger.info("Got 413 error, attempting Dropbox upload as fallback")
                        filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                        dropbox_link = await upload_to_dropbox(file_path, filename)

                        if dropbox_link:
                            await send_message(
                                message.chat.id,
                                f"⚠️ **File too large for Telegram.**\n📥 [Download from Dropbox]({dropbox_link})"
                            )
                        else:
                            await send_message(message.chat.id, "❌ **File too large and Dropbox upload failed.**")
                    else:
                        await send_message(message.chat.id, f"❌ **Error sending file: {str(send_error)}**")

            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Cleaned up file: {file_path}")
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up file {file_path}: {cleanup_error}")

        gc.collect()

    except Exception as e:
        logger.error(f"Comprehensive error in process_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

async def process_image_download(message, url):
    """Handles image download and sends it to Telegram or Dropbox."""
    try:
        await send_message(message.chat.id, "🖼️ Processing Instagram image...")
        logger.info(f"Processing Instagram image URL: {url}")
        # Process the Instagram image
        try:
            result = await process_instagram_image(url)

            # Handle different return formats
            if isinstance(result, list):
                file_paths = result
            elif isinstance(result, tuple) and len(result) >= 2:
                file_paths = result[0] if isinstance(result[0], list) else [result[0]]
            else:
                file_paths = [result] if result else []

            if not file_paths or all(not path for path in file_paths):
                logger.warning("No valid image paths returned from Instagram handler")
                await send_message(message.chat.id, "❌ **Download failed. No images found.**")
                return

            # Process each image
            for file_path in file_paths:
                if not file_path or not os.path.exists(file_path):
                    logger.warning(f"Image path does not exist: {file_path}")
                    continue

                # Get file size
                file_size = os.path.getsize(file_path)

                # Handle case where file is too large for Telegram
                if file_size > TELEGRAM_FILE_LIMIT:
                    filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                    logger.info(f"Image too large for Telegram: {file_size} bytes. Using Dropbox.")

                    # Upload to Dropbox
                    dropbox_link = await upload_to_dropbox(file_path, filename)

                    if dropbox_link:
                        logger.info(f"Successfully uploaded image to Dropbox: {dropbox_link}")
                        await send_message(
                            message.chat.id,
                            f"⚠️ **Image too large for Telegram.**\n📥 [Download from Dropbox]({dropbox_link})",
                            parse_mode="Markdown"
                        )
                    else:
                        logger.warning("Dropbox upload failed")
                        await send_message(message.chat.id, "❌ **Image download failed.**")
                else:
                    # Send image to Telegram
                    try:
                        async with aiofiles.open(file_path, "rb") as file:
                            file_content = await file.read()
                            await bot.send_photo(message.chat.id, file_content, timeout=60)
                            logger.info(f"Successfully sent image to Telegram")
                    except Exception as send_error:
                        logger.error(f"Error sending image to Telegram: {send_error}")
                        await send_message(message.chat.id, f"❌ **Error sending image: {str(send_error)}**")

                # Cleanup the file
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Cleaned up image file: {file_path}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up image file {file_path}: {cleanup_error}")

            # Send success message
            await send_message(message.chat.id, "✅ **Instagram image(s) downloaded successfully!**")

        except Exception as e:
            logger.error(f"Error processing Instagram image: {e}", exc_info=True)
            await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Comprehensive error in process_image_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

# Worker for parallel download tasks
async def worker():
    """Worker function for parallel processing of downloads."""
    while True:
        try:
            # Check if shutdown is requested
            if shutdown_event.is_set():
                logger.info("Worker shutting down")
                break
                
            # Wait for a task with timeout to check shutdown periodically
            try:
                task = await asyncio.wait_for(download_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
                
            if len(task) == 2:
                # Image processing task
                message, url = task
                await process_image_download(message, url)
            else:
                # Regular download task
                message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time = task
                await process_download(message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time)

            download_queue.task_done()
        except Exception as e:
            logger.error(f"Error in worker: {e}")
            # Continue the loop to process other tasks even if one fails

# Start/help command
@bot.message_handler(commands=["start", "help"])
async def send_welcome(message):
    """Sends welcome message with bot instructions."""
    welcome_text = (
        "🤖 Media Download Bot 🤖\n\n"
        "I can help you download media from various platforms:\n"
        "• YouTube\n• Instagram\n• Facebook\n• Twitter/X\n\n"
        "Commands:\n"
        "• Send a direct URL to download video\n"
        "• /audio <URL> - Extract full audio from video\n"
        "• /image <URL> - Download Instagram images\n"
        "• /trim <URL> <Start Time> <End Time> - Trim video segment\n"
        "• /trimAudio <URL> <Start Time> <End Time> - Extract audio segment\n\n"
        "Examples:\n"
        "• /image https://instagram.com/p/example\n"
        "• /trim https://youtube.com/watch?v=example 00:01:00 00:02:30\n"
        "• /trimAudio https://youtube.com/watch?v=example 00:01:00 00:02:30"
    )
    await bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

# Audio extraction handler
@bot.message_handler(commands=["audio"])
async def handle_audio_request(message):
    """Handles audio extraction requests for all platforms."""
    url = message.text.replace("/audio", "").strip()
    if not url:
        await send_message(message.chat.id, "⚠️ Please provide a URL.")
        return
    await download_queue.put((message, url, True, False, False, None, None))
    await send_message(message.chat.id, "🎵 Added to audio extraction queue!")

# Instagram image download handler
@bot.message_handler(commands=["image"])
async def handle_image_request(message):
    """Handles Instagram image download requests."""
    url = message.text.replace("/image", "").strip()
    if not url:
        await send_message(message.chat.id, "⚠️ Please provide an Instagram image URL.")
        return

    # Check if URL is Instagram
    if not PLATFORM_PATTERNS["Instagram"].search(url):
        await send_message(message.chat.id, "⚠️ **This command only works with Instagram image URLs.**")
        return

    # Add to download queue
    await download_queue.put((message, url))
    await send_message(message.chat.id, "🖼️ **Added to image download queue!**")

# Video trim handler
@bot.message_handler(commands=["trim"])
async def handle_video_trim_request(message):
    """Handles video trimming requests."""
    match = re.search(r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", message.text)
    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format. Please send: /trim <URL> <Start Time (HH:MM:SS)> <End Time (HH:MM:SS)>"
        )
        return

    url, start_time, end_time = match.groups()
    await download_queue.put((message, url, False, True, False, start_time, end_time))
    await send_message(message.chat.id, "✂️🎬 **Added to video trimming queue!**")

# Audio trim handler
@bot.message_handler(commands=["trimAudio"])
async def handle_audio_trim_request(message):
    """Handles audio segment extraction requests."""
    match = re.search(r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", message.text)
    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format. Please send: /trimAudio <URL> <Start Time (HH:MM:SS)> <End Time (HH:MM:SS)>"
        )
        return

    url, start_time, end_time = match.groups()
    await download_queue.put((message, url, False, False, True, start_time, end_time))
    await send_message(message.chat.id, "✂️🎵 **Added to audio segment extraction queue!**")

# General message handler
@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    """Handles general video download requests."""
    url = message.text.strip()
    await download_queue.put((message, url, False, False, False, None, None))
    await send_message(message.chat.id, "🎬 Added to video download queue!")

# Health check endpoint
async def health_check(request):
    """Simple health check handler that returns 200 OK if the bot is running."""
    if bot_running:
        return web.Response(text="OK", status=200)
    else:
        return web.Response(text="Bot not running", status=503)

# Graceful shutdown handler
async def shutdown(app):
    """Handle graceful shutdown."""
    global bot_running
    logger.info("Shutting down bot...")
    bot_running = False
    
    # Signal worker tasks to exit
    shutdown_event.set()
    
    # Wait for queue to be processed
    if not download_queue.empty():
        logger.info(f"Waiting for {download_queue.qsize()} tasks to complete...")
        try:
            await asyncio.wait_for(download_queue.join(), timeout=30.0)
            logger.info("All tasks completed successfully")
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for tasks to complete")
    
    logger.info("Bot shutdown complete")

# Signal handlers
def handle_signals():
    """Set up signal handlers for graceful shutdown."""
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: asyncio.create_task(shutdown_app()))

async def shutdown_app():
    """Shut down the application."""
    logger.info("Received shutdown signal")
    await shutdown(None)  # Pass None as we're not using the app parameter
    asyncio.get_event_loop().stop()

async def setup_web_server():
    """Set up aiohttp web server for health checks."""
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)  # Root path for simple checks
    
    # Handle graceful shutdown
    app.on_shutdown.append(shutdown)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Use port 8080 which appears to be the required port for your health checks
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Health check server started on port 8080")
    return runner

async def run_polling():
    """Run the bot polling with proper error handling."""
    global bot_running
    bot_running = True
    
    # Maximum number of retries before giving up
    max_retries = 5
    retry_count = 0
    
    while bot_running and retry_count < max_retries:
        try:
            logger.info("Starting bot polling")
            await bot.polling(timeout=30, non_stop=True, skip_pending=True)
        except Exception as e:
            retry_count += 1
            if "terminated by other getUpdates request" in str(e):
                logger.warning(f"409 Conflict error detected, sleeping before retry {retry_count}/{max_retries}")
                await asyncio.sleep(10)  # Wait before retrying to allow other instances to terminate
            else:
                logger.error(f"Bot polling error: {e}", exc_info=True)
                if retry_count >= max_retries:
                    logger.critical(f"Maximum retry attempts reached ({max_retries}), stopping bot")
                    break
                await asyncio.sleep(5)  # Wait before retrying for other errors
    
    bot_running = False
    logger.info("Bot polling stopped")

# Main bot runner
async def main():
    """Runs the bot and initializes worker processes."""
    # Check token validity at startup
    await token_manager.refresh_if_needed()
    
    # Setup signal handlers
    handle_signals()
    
    # Start health check server
    web_runner = await setup_web_server()
    
    # Start worker tasks
    num_workers = min(3, os.cpu_count() or 1)
    worker_tasks = []
    for _ in range(num_workers):
        worker_tasks.append(asyncio.create_task(worker()))
    
    # Start the bot polling
    try:
        await run_polling()
    finally:
        # Ensure shutdown is triggered
        global bot_running
        bot_running = False
        shutdown_event.set()