import os
import gc
import logging
import asyncio
import aiofiles
import re
# Remove Dropbox imports
# import dropbox
# from dropbox.exceptions import AuthError, ApiError
from telebot.async_telebot import AsyncTeleBot
from mega import Mega # Import Mega library

# Import local modules
# Make sure to add MEGA_EMAIL and MEGA_PASSWORD to your config
from config import API_TOKEN, TELEGRAM_FILE_LIMIT, MEGA_EMAIL, MEGA_PASSWORD
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

# --- Mega.nz client setup ---
mega = None
mega_logged_in = False
mega_upload_folder_node = None # To store the target folder node

async def initialize_mega():
    """Initializes and logs into Mega.nz."""
    global mega, mega_logged_in, mega_upload_folder_node
    if mega_logged_in:
        return True

    try:
        logger.info("Initializing Mega.nz client...")
        mega = Mega()
        logger.info("Attempting Mega.nz login...")
        # Run login in a separate thread to avoid blocking asyncio loop
        m = await asyncio.to_thread(mega.login, MEGA_EMAIL, MEGA_PASSWORD)
        logger.info("Mega.nz login successful.")
        mega_logged_in = True

        # Find or create the upload folder
        folder_name = "telegram_bot_uploads"
        logger.info(f"Looking for Mega folder: {folder_name}")
        # Run find/create folder in a separate thread
        folder_node_list = await asyncio.to_thread(m.find, folder_name, exclude_deleted=True)

        if folder_node_list and isinstance(folder_node_list, tuple) and len(folder_node_list) > 1:
             # m.find returns a tuple: (node_dict, type) if found
             mega_upload_folder_node = folder_node_list[0] # Get the node dictionary
             logger.info(f"Found Mega folder node: {mega_upload_folder_node}")
        else:
             logger.info(f"Mega folder '{folder_name}' not found. Creating...")
             # Run create folder in a separate thread
             await asyncio.to_thread(m.create_folder, folder_name)
             logger.info(f"Mega folder '{folder_name}' created.")
             # Find it again to get the node
             folder_node_list = await asyncio.to_thread(m.find, folder_name, exclude_deleted=True)
             if folder_node_list and isinstance(folder_node_list, tuple) and len(folder_node_list) > 1:
                  mega_upload_folder_node = folder_node_list[0]
                  logger.info(f"Using newly created Mega folder node: {mega_upload_folder_node}")
             else:
                  logger.error(f"Failed to find or create Mega folder '{folder_name}'. Uploads will go to root.")
                  mega_upload_folder_node = await asyncio.to_thread(m.find, m.root) # Fallback to root

        return True

    except Exception as e:
        logger.error(f"Mega.nz initialization/login failed: {e}", exc_info=True)
        mega_logged_in = False
        return False

# Regex patterns for different platforms (keep as is)
PLATFORM_PATTERNS = {
    "YouTube": re.compile(r"(youtube\.com|youtu\.be)"),
    "Instagram": re.compile(r"instagram\.com"),
    "Facebook": re.compile(r"facebook\.com"),
    "Twitter/X": re.compile(r"(x\.com|twitter\.com)"),
    "Adult": re.compile(r"(pornhub\.com|xvideos\.com|redtube\.com|xhamster\.com|xnxx\.com)"),
}

# Platform handlers (keep as is)
PLATFORM_HANDLERS = {
    "YouTube": process_youtube,
    "Instagram": process_instagram,
    "Facebook": process_facebook,
    "Twitter/X": download_twitter_media,
    "Adult": process_adult,
}

async def send_message(chat_id, text, **kwargs): # Added **kwargs for parse_mode etc.
    """Sends a message asynchronously."""
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logger.error(f"Error sending message: {e}")


def detect_platform(url):
    """Detects the platform based on URL patterns."""
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None


# --- Replaced upload_to_dropbox with upload_to_mega ---
async def upload_to_mega(file_path, filename):
    """
    Uploads a file to Mega.nz and returns a shareable link.

    Args:
        file_path (str): Path to the file to upload.
        filename (str): Base name for the file (used for logging).

    Returns:
        str: Shareable link to the uploaded file, or None on failure.
    """
    global mega, mega_logged_in, mega_upload_folder_node
    if not mega_logged_in:
        logger.error("Mega client not logged in. Cannot upload.")
        if not await initialize_mega(): # Attempt re-login
             logger.error("Mega re-login attempt failed during upload.")
             return None

    try:
        logger.info(f"Attempting to upload {filename} to Mega.nz...")
        # Use asyncio.to_thread to run the blocking mega.py upload call
        uploaded_file = await asyncio.to_thread(
            mega.upload,
            file_path,
            mega_upload_folder_node # Upload to the specific folder node
        )

        if not uploaded_file:
            logger.error(f"Mega.nz upload failed for {filename}.")
            return None

        logger.info(f"Successfully uploaded {filename}. Generating export link...")

        # Use asyncio.to_thread for the blocking export call
        link = await asyncio.to_thread(mega.export, uploaded_file)

        if not link:
             logger.error(f"Failed to generate Mega.nz export link for {filename}.")
             return None

        logger.info(f"Mega.nz link generated: {link}")
        return link

    except Exception as e:
        logger.error(f"Unexpected Mega.nz upload/export error for {filename}: {e}", exc_info=True)
        # Attempt re-login in case of session issues
        mega_logged_in = False # Assume login might be invalid
        return None

async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    """Handles video/audio download and sends it to Telegram or Mega.nz."""
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

        # Handle request based on type (logic remains mostly the same)
        file_paths = []
        file_size = None
        download_url = None # Keep track of original download URL if available

        if is_video_trim:
            logger.info(f"Processing video trim request: Start={start_time}, End={end_time}")
            file_path, file_size = await process_video_trim(url, start_time, end_time)
            file_paths = [file_path] if file_path else []

        elif is_audio_trim:
            logger.info(f"Processing audio trim request: Start={start_time}, End={end_time}")
            file_path, file_size = await process_audio_trim(url, start_time, end_time)
            file_paths = [file_path] if file_path else []

        elif is_audio:
            result = await extract_audio_ffmpeg(url)
            if isinstance(result, tuple):
                file_path, file_size = result if len(result) == 2 else (result[0], None)
                file_paths = [file_path] if file_path else []
            else: # Assuming result might be just the path
                file_path = result
                file_size = None
                file_paths = [file_path] if file_path else []


        else: # Regular Video/Media download
            if platform == "Instagram":
                 # Differentiate between post/story (image/video) and reel/igtv (video)
                 if "/p/" in url or "/stories/" in url:
                      # Might return images or videos, handle list return
                      result = await process_instagram_image(url) # Reuse image handler which can get videos too
                 elif "/reel/" in url or "/tv/" in url:
                      result = await process_instagram(url) # Primarily video handler
                 else: # Fallback for other possible instagram url types
                      result = await process_instagram(url)
            else:
                result = await PLATFORM_HANDLERS[platform](url)

            # Handle different return formats carefully
            if isinstance(result, tuple) and len(result) >= 3: # path(s), size, url
                temp_paths, file_size, download_url = result
                file_paths = temp_paths if isinstance(temp_paths, list) else [temp_paths] if temp_paths else []
            elif isinstance(result, tuple) and len(result) == 2: # path(s), size
                temp_paths, file_size = result
                file_paths = temp_paths if isinstance(temp_paths, list) else [temp_paths] if temp_paths else []
                download_url = None
            elif isinstance(result, list): # list of paths
                 file_paths = result
                 file_size = None # Need to calculate later
                 download_url = None
            else: # single path
                file_paths = [result] if result else []
                file_size = None # Need to calculate later
                download_url = None

        logger.info(f"Platform handler returned: file_paths={file_paths}, file_size={file_size}, download_url={download_url}")

        if not file_paths or all(not path for path in file_paths):
            logger.warning("No valid file paths returned from platform handler")
            await send_message(message.chat.id, "❌ **Download failed. No media found.**")
            return

        for file_path in file_paths:
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"File path does not exist or is invalid: {file_path}")
                continue

            current_file_size = file_size if file_size is not None else os.path.getsize(file_path) # Use known size or get it

            # Use Mega.nz if file is too large for Telegram
            # Reduced limit slightly to be safer (48MB)
            if current_file_size > (TELEGRAM_FILE_LIMIT - 2 * 1024 * 1024):
                filename_base = os.path.basename(file_path)
                logger.info(f"File too large for Telegram: {current_file_size} bytes. Uploading to Mega.nz.")

                # --- Call upload_to_mega ---
                mega_link = await upload_to_mega(file_path, filename_base)

                if mega_link:
                    logger.info(f"Successfully uploaded to Mega.nz: {mega_link}")
                    await send_message(
                        message.chat.id,
                        f"⚠️ **File too large for Telegram.**\n📥 [Download from Mega.nz]({mega_link})",
                        parse_mode="Markdown" # Make sure Markdown works for links
                    )
                else:
                    logger.warning("Mega.nz upload failed")
                    # Fallback to original download URL if available and upload failed
                    if download_url:
                         await send_message(
                              message.chat.id,
                              f"⚠️ **File too large & Mega upload failed.**\n"
                              f"📥 [Try Original Source Link]({download_url})",
                              parse_mode="Markdown"
                         )
                    else:
                         await send_message(message.chat.id, "❌ **File too large and failed to upload to Mega.nz.**")

            else: # File size is okay for Telegram
                try:
                    async with aiofiles.open(file_path, "rb") as file:
                        file_content = await file.read()
                        file_size_actual = len(file_content) # Double check size

                        if file_size_actual > TELEGRAM_FILE_LIMIT:
                            logger.warning(f"Actual read size {file_size_actual} exceeds limit, switching to Mega.nz")
                            filename_base = os.path.basename(file_path)
                            # --- Call upload_to_mega again ---
                            mega_link = await upload_to_mega(file_path, filename_base)

                            if mega_link:
                                await send_message(
                                    message.chat.id,
                                    f"⚠️ **File too large for Telegram.**\n📥 [Download from Mega.nz]({mega_link})",
                                    parse_mode="Markdown"
                                )
                            else:
                                await send_message(message.chat.id, "❌ **File too large and failed to upload to Mega.nz.**")

                        # Send to Telegram
                        elif is_audio or is_audio_trim or file_path.lower().endswith(('.mp3', '.m4a', '.ogg', '.flac')):
                            await bot.send_audio(message.chat.id, file_content, timeout=600)
                        elif file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp')):
                             await bot.send_photo(message.chat.id, file_content, timeout=120)
                        else: # Assume video
                            await bot.send_video(message.chat.id, file_content, supports_streaming=True, timeout=600)

                except Exception as send_error:
                    logger.error(f"Error sending file {os.path.basename(file_path)} to Telegram: {send_error}")
                    # Handle Telegram specific "Too Large" error (413)
                    if "413" in str(send_error) or "too large" in str(send_error).lower():
                        logger.info("Telegram reported file too large (413), attempting Mega.nz upload.")
                        filename_base = os.path.basename(file_path)
                        # --- Call upload_to_mega as fallback ---
                        mega_link = await upload_to_mega(file_path, filename_base)

                        if mega_link:
                            await send_message(
                                message.chat.id,
                                f"⚠️ **File too large for Telegram.**\n📥 [Download from Mega.nz]({mega_link})",
                                parse_mode="Markdown"
                            )
                        else:
                            await send_message(message.chat.id, "❌ **File too large and Mega.nz upload failed.**")
                    else:
                        await send_message(message.chat.id, f"❌ **Error sending file:** `{str(send_error)}`")

            # Cleanup the local file
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Cleaned up file: {file_path}")
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up file {file_path}: {cleanup_error}")

        gc.collect() # Garbage collection

    except Exception as e:
        logger.error(f"Comprehensive error in process_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")


async def process_image_download(message, url):
    """Handles image download and sends it to Telegram or Mega.nz."""
    try:
        await send_message(message.chat.id, "🖼️ Processing Instagram image/post...")
        logger.info(f"Processing Instagram image/post URL: {url}")

        try:
            # Use process_instagram_image which might return multiple file types (image/video)
            result = await process_instagram_image(url)

            # Handle different return formats from process_instagram_image
            if isinstance(result, list):
                 file_paths = result
            elif isinstance(result, tuple) and len(result) >= 1: # Expecting (list_of_paths, maybe_size)
                 file_paths = result[0] if isinstance(result[0], list) else [result[0]] if result[0] else []
            else:
                 file_paths = [result] if result else []


            if not file_paths or all(not path for path in file_paths):
                logger.warning("No valid image/media paths returned from Instagram handler")
                await send_message(message.chat.id, "❌ **Download failed. No images or videos found in post.**")
                return

            sent_success_message = False
            for file_path in file_paths:
                if not file_path or not os.path.exists(file_path):
                    logger.warning(f"Media path does not exist: {file_path}")
                    continue

                file_size = os.path.getsize(file_path)
                filename_base = os.path.basename(file_path)

                # Use Mega.nz if file is too large
                if file_size > (TELEGRAM_FILE_LIMIT - 2 * 1024 * 1024):
                    logger.info(f"Media {filename_base} too large for Telegram: {file_size} bytes. Uploading to Mega.nz.")
                    # --- Call upload_to_mega ---
                    mega_link = await upload_to_mega(file_path, filename_base)

                    if mega_link:
                        logger.info(f"Successfully uploaded media to Mega.nz: {mega_link}")
                        await send_message(
                            message.chat.id,
                            f"⚠️ **Media file too large for Telegram.**\n📥 [Download from Mega.nz]({mega_link})",
                            parse_mode="Markdown"
                        )
                        sent_success_message = True # Mark as success even if uploaded externally
                    else:
                        logger.warning("Mega.nz upload failed")
                        await send_message(message.chat.id, f"❌ **Media file {filename_base} too large and Mega upload failed.**")
                else:
                    # Send media to Telegram
                    try:
                        async with aiofiles.open(file_path, "rb") as file:
                            file_content = await file.read()
                            # Send as photo or video based on extension
                            if filename_base.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp')):
                                 await bot.send_photo(message.chat.id, file_content, timeout=120)
                            elif filename_base.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                                 await bot.send_video(message.chat.id, file_content, timeout=600)
                            else:
                                 logger.warning(f"Unknown file type for Telegram sending: {filename_base}, sending as document.")
                                 await bot.send_document(message.chat.id, file_content, timeout=600)

                            logger.info(f"Successfully sent media {filename_base} to Telegram")
                            sent_success_message = True
                    except Exception as send_error:
                        logger.error(f"Error sending media {filename_base} to Telegram: {send_error}")
                        if "413" in str(send_error) or "too large" in str(send_error).lower():
                             logger.info(f"Telegram reported {filename_base} too large (413), attempting Mega.nz upload.")
                             # --- Call upload_to_mega as fallback ---
                             mega_link = await upload_to_mega(file_path, filename_base)
                             if mega_link:
                                  await send_message(
                                       message.chat.id,
                                       f"⚠️ **Media file too large for Telegram.**\n📥 [Download from Mega.nz]({mega_link})",
                                       parse_mode="Markdown"
                                  )
                                  sent_success_message = True
                             else:
                                  await send_message(message.chat.id, f"❌ **Media {filename_base} too large and Mega upload failed.**")
                        else:
                             await send_message(message.chat.id, f"❌ **Error sending media {filename_base}:** `{str(send_error)}`")


                # Cleanup the file
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Cleaned up media file: {file_path}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up media file {file_path}: {cleanup_error}")

            # Send a single success message if at least one file was processed ok
            if sent_success_message:
                 await send_message(message.chat.id, "✅ **Instagram post media processed!**")
            else:
                 # If loop finished but nothing succeeded (e.g., all files failed upload)
                 logger.info("Finished processing images, but no success message was sent.")
                 # Optionally send a generic failure message if needed, but might be redundant
                 # await send_message(message.chat.id, "❌ **Failed to process all media from the post.**")


        except Exception as e:
            logger.error(f"Error processing Instagram post/image: {e}", exc_info=True)
            await send_message(message.chat.id, f"❌ **An error occurred processing the Instagram post:** `{e}`")

    except Exception as e:
        logger.error(f"Comprehensive error in process_image_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An unexpected error occurred:** `{e}`")

# Worker for parallel download tasks
async def worker():
    """Worker function for parallel processing of downloads."""
    # Ensure Mega is initialized within the worker's loop context if needed,
    # but the global initialization in main() should be sufficient.
    if not mega_logged_in:
        logger.info("Worker started, ensuring Mega client is initialized...")
        await initialize_mega() # Ensure it's ready before processing tasks

    while True:
        task = await download_queue.get()
        logger.info(f"Worker received task: {task[0].text if hasattr(task[0], 'text') else 'Unknown task type'}") # Log task receipt

        try:
             # Check task structure to differentiate image vs other downloads
             if len(task) == 2 and isinstance(task[1], str) and PLATFORM_PATTERNS["Instagram"].search(task[1]):
                 # Assume it's an image task if 2 args and URL looks like Instagram
                 message, url = task
                 # Check if the command was /image explicitly
                 is_explicit_image_command = message.text.startswith("/image")
                 if is_explicit_image_command:
                      await process_image_download(message, url)
                 else:
                      # If just an Instagram URL was sent, use the general process_download
                      # which now also handles Instagram posts/stories via process_instagram_image
                      await process_download(message, url, False, False, False, None, None)

             elif len(task) == 7: # Matches the structure for video/audio/trim tasks
                  # Regular download/trim task
                  message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time = task
                  await process_download(message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time)
             else:
                  logger.warning(f"Worker received unknown task format: {task}")


        except Exception as worker_error:
             logger.error(f"Error occurred processing task in worker: {worker_error}", exc_info=True)
             # Try to inform the user if possible
             if hasattr(task[0], 'chat') and hasattr(task[0].chat, 'id'):
                  await send_message(task[0].chat.id, f"❌ An internal error occurred processing your request.")

        finally:
             download_queue.task_done()
             gc.collect() # Run garbage collection after each task


# Start/help command (keep as is)
@bot.message_handler(commands=["start", "help"])
async def send_welcome(message):
    """Sends welcome message with bot instructions."""
    welcome_text = (
        "🤖 Media Download Bot 🤖\n\n"
        "I can help you download media from:\n"
        "• YouTube\n• Instagram (Posts, Stories, Reels, IGTV)\n• Facebook\n• Twitter/X\n\n" # Removed Adult mention for safety
        "➡️ **How to Use:**\n"
        "1. Just send me the URL of the media!\n"
        "2. For large files (>48MB), I'll upload to Mega.nz and give you a link.\n\n"
        "⚙️ **Specific Commands:**\n"
        "`/audio <URL>` - Extract full audio\n"
        "`/image <URL>` - Download all images/videos from an Instagram post/story URL\n"
        "`/trim <URL> <HH:MM:SS> <HH:MM:SS>` - Trim video\n"
        "`/trimAudio <URL> <HH:MM:SS> <HH:MM:SS>` - Trim audio\n\n"
        "✂️ **Trim Examples:**\n"
        "`/trim https://youtu.be/example 00:00:30 00:01:15`\n"
        "`/trimAudio https://facebook.com/watch/video_id 0:10:05 0:12:00`" # Added FB example
    )
    # Use Markdown for better formatting
    await bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

# Audio extraction handler (keep as is)
@bot.message_handler(commands=["audio"])
async def handle_audio_request(message):
    """Handles audio extraction requests for all platforms."""
    url = message.text.replace("/audio", "").strip()
    if not url:
        await send_message(message.chat.id, "⚠️ Please provide a URL after `/audio`.")
        return
    # Use the 7-tuple format for the queue
    await download_queue.put((message, url, True, False, False, None, None))
    await send_message(message.chat.id, "🎵 Added URL to audio extraction queue!")

# Instagram image download handler (Modified slightly for clarity)
@bot.message_handler(commands=["image"])
async def handle_image_request(message):
    """Handles Instagram post/story download requests."""
    url = message.text.replace("/image", "").strip()
    if not url:
        await send_message(message.chat.id, "⚠️ Please provide an Instagram URL after `/image` (e.g., `/image https://instagram.com/p/abc...`).")
        return

    # Check if URL is Instagram
    if not PLATFORM_PATTERNS["Instagram"].search(url):
        await send_message(message.chat.id, "⚠️ **This command currently only supports Instagram post/story URLs.**")
        return

    # Add to download queue using the 2-tuple format specifically for image command
    await download_queue.put((message, url))
    await send_message(message.chat.id, "🖼️ **Added Instagram post/story URL to the download queue!**")


# Video trim handler (keep as is)
@bot.message_handler(commands=["trim"])
async def handle_video_trim_request(message):
    """Handles video trimming requests."""
    # Improved regex to be more flexible with spacing
    match = re.search(r"/trim\s+(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", message.text, re.IGNORECASE)
    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format. Use:\n`/trim <URL> <StartTime> <EndTime>`\n"
            "Example: `/trim https://... 00:00:10 00:00:55`",
             parse_mode="Markdown" # Use markdown for formatting
        )
        return

    url, start_time, end_time = match.groups()
    # Use the 7-tuple format for the queue
    await download_queue.put((message, url, False, True, False, start_time, end_time))
    await send_message(message.chat.id, "✂️🎬 **Added video trimming task to the queue!**")

# Audio trim handler (keep as is)
@bot.message_handler(commands=["trimAudio"])
async def handle_audio_trim_request(message):
    """Handles audio segment extraction requests."""
     # Improved regex to be more flexible with spacing
    match = re.search(r"/trimAudio\s+(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", message.text, re.IGNORECASE)
    if not match:
        await send_message(
            message.chat.id,
             "⚠️ Invalid format. Use:\n`/trimAudio <URL> <StartTime> <EndTime>`\n"
             "Example: `/trimAudio https://... 00:01:00 00:01:30`",
             parse_mode="Markdown" # Use markdown for formatting
        )
        return

    url, start_time, end_time = match.groups()
    # Use the 7-tuple format for the queue
    await download_queue.put((message, url, False, False, True, start_time, end_time))
    await send_message(message.chat.id, "✂️🎵 **Added audio trimming task to the queue!**")

# General message handler (Modified to check for commands first)
@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message):
    """Handles general text messages (likely URLs for download)."""
    # Ignore commands handled by specific handlers
    if message.text.startswith('/'):
        # Optional: Send a message indicating unknown command, or just ignore
        # await send_message(message.chat.id, "❓ Unknown command. Send /help for instructions.")
        logger.info(f"Ignoring command message: {message.text}")
        return

    url = message.text.strip()
    # Basic URL validation (optional but recommended)
    if not re.match(r"https?://", url):
         await send_message(message.chat.id, "🤔 That doesn't look like a valid URL. Please send a direct link to the media.")
         return

    # Add general URLs to the download queue using the 7-tuple format
    await download_queue.put((message, url, False, False, False, None, None))
    await send_message(message.chat.id, "🎬 Added URL to the download queue!")

# Main bot runner
async def main():
    """Runs the bot and initializes worker processes."""
    # Initialize Mega.nz client first
    if not await initialize_mega():
        logger.critical("Failed to initialize Mega.nz client on startup. Exiting.")
        # Optionally, allow the bot to run without Mega uploads, but log critical error.
        # return # Uncomment to exit if Mega login fails

    # Start worker tasks
    num_workers = min(3, os.cpu_count() or 1) # Keep worker count reasonable
    logger.info(f"Starting {num_workers} download workers...")
    worker_tasks = []
    for i in range(num_workers):
        task = asyncio.create_task(worker())
        worker_tasks.append(task)
        logger.info(f"Worker {i+1} started.")

    try:
        logger.info("Starting Telegram bot polling...")
        await bot.infinity_polling(timeout=30, logger_level=logging.INFO) # Use INFO level for polling logs
    except Exception as e:
        logger.critical(f"Bot polling loop encountered a critical error: {e}", exc_info=True)
    finally:
        logger.info("Bot polling stopped. Cancelling worker tasks...")
        for task in worker_tasks:
            task.cancel()
        await asyncio.gather(*worker_tasks, return_exceptions=True) # Wait for workers to finish cancelling
        logger.info("Workers cancelled.")
        # Perform mega logout if necessary (mega.py might handle this on exit)
        # if mega_logged_in and mega:
        #     try:
        #         # mega.logout() # Check if logout() exists and is needed
        #         pass
        #     except Exception as logout_err:
        #         logger.error(f"Error during Mega logout: {logout_err}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually (KeyboardInterrupt).")
