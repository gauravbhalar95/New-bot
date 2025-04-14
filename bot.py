import os
import gc
import logging
import asyncio
import aiofiles
import re
from typing import Optional, List, Tuple, Any, Dict # Added for type hinting

# --- External Dependencies ---
# pip install pyTelegramBotAPI mega.py aiofiles
# Ensure mega.py is compatible with Python 3.13, check its PyPI page if issues arise.
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message # Added for type hinting
from mega import Mega # Import Mega library

# --- Local Modules ---
# Create a 'config.py' file in the same directory with these variables:
# API_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
# TELEGRAM_FILE_LIMIT = 50 * 1024 * 1024  # 50 MB Telegram limit
# MEGA_EMAIL = "YOUR_MEGA_EMAIL"
# MEGA_PASSWORD = "YOUR_MEGA_PASSWORD"
try:
    from config import API_TOKEN, TELEGRAM_FILE_LIMIT, MEGA_EMAIL, MEGA_PASSWORD
except ImportError:
    print("ERROR: config.py not found or missing required variables.")
    print("Please create config.py with API_TOKEN, TELEGRAM_FILE_LIMIT, MEGA_EMAIL, MEGA_PASSWORD")
    exit(1)

# Import local handlers (assuming they are in a 'handlers' subdirectory)
# Ensure these handlers are also compatible.
try:
    from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
    from handlers.instagram_handler import process_instagram, process_instagram_image
    from handlers.facebook_handlers import process_facebook
    from handlers.common_handler import process_adult
    from handlers.x_handler import download_twitter_media
    from handlers.trim_handlers import process_video_trim, process_audio_trim
    # from handlers.image_handlers import process_instagram_image # Already imported above
    from utils.logger import setup_logging # Assuming logger setup is in utils
except ImportError as e:
    print(f"ERROR: Failed to import handlers or utils: {e}")
    print("Ensure handlers/*.py and utils/logger.py exist and are correct.")
    exit(1)


# --- Constants ---
MEGA_UPLOAD_THRESHOLD = TELEGRAM_FILE_LIMIT - (2 * 1024 * 1024) # 2MB buffer
MEGA_FOLDER_NAME = "telegram_bot_uploads"

# --- Logging Setup ---
logger = setup_logging(logging.DEBUG)

# --- Async Telegram Bot Setup ---
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue: asyncio.Queue = asyncio.Queue()

# --- Mega.nz Client Setup ---
mega: Optional[Mega] = None
mega_logged_in: bool = False
mega_upload_folder_node: Optional[Dict[str, Any]] = None # To store the target folder node

async def initialize_mega() -> bool:
    """Initializes and logs into Mega.nz."""
    global mega, mega_logged_in, mega_upload_folder_node
    if mega_logged_in:
        return True

    try:
        logger.info("Initializing Mega.nz client...")
        mega = Mega()
        logger.info(f"Attempting Mega.nz login ({MEGA_EMAIL})...")
        # Run blocking login in a separate thread
        m = await asyncio.to_thread(mega.login, MEGA_EMAIL, MEGA_PASSWORD)
        logger.info("Mega.nz login successful.")
        mega_logged_in = True

        # Find or create the upload folder
        logger.info(f"Looking for Mega folder: {MEGA_FOLDER_NAME}")
        # Run blocking find/create folder in a separate thread
        folder_node_tuple = await asyncio.to_thread(m.find, MEGA_FOLDER_NAME, exclude_deleted=True)

        if folder_node_tuple and isinstance(folder_node_tuple, tuple) and len(folder_node_tuple) > 0:
             # m.find returns a tuple: ((node_dict, type),) if found, or None
             # Or just (node_dict, type) in older versions? Check mega.py docs if needed.
             # Let's assume the primary node is the first element of the first tuple item
             if isinstance(folder_node_tuple[0], tuple) and len(folder_node_tuple[0]) > 0:
                  mega_upload_folder_node = folder_node_tuple[0][0] # Get the node dictionary
                  logger.info(f"Found Mega folder node: {mega_upload_folder_node.get('h', 'N/A')}") # Log handle 'h'
             else:
                  # Fallback if the structure is different (e.g., just (node, type))
                  mega_upload_folder_node = folder_node_tuple[0]
                  logger.info(f"Found Mega folder node (alternative structure): {mega_upload_folder_node.get('h', 'N/A')}")
        else:
             logger.info(f"Mega folder '{MEGA_FOLDER_NAME}' not found. Creating...")
             # Run blocking create folder in a separate thread
             # Note: m.create_folder returns a list of nodes created [{...}]
             created_folder_list = await asyncio.to_thread(m.create_folder, MEGA_FOLDER_NAME)
             if created_folder_list:
                 logger.info(f"Mega folder '{MEGA_FOLDER_NAME}' created.")
                 # Find it again to get the node in the expected format
                 folder_node_tuple = await asyncio.to_thread(m.find, MEGA_FOLDER_NAME, exclude_deleted=True)
                 if folder_node_tuple and isinstance(folder_node_tuple[0], tuple) and len(folder_node_tuple[0]) > 0:
                      mega_upload_folder_node = folder_node_tuple[0][0]
                      logger.info(f"Using newly created Mega folder node: {mega_upload_folder_node.get('h', 'N/A')}")
                 elif folder_node_tuple: # Alternative structure check
                      mega_upload_folder_node = folder_node_tuple[0]
                      logger.info(f"Using newly created Mega folder node (alternative structure): {mega_upload_folder_node.get('h', 'N/A')}")
                 else:
                     logger.error(f"Failed to find created Mega folder '{MEGA_FOLDER_NAME}'. Uploads will go to root.")
                     mega_upload_folder_node = await asyncio.to_thread(m.get_root_node) # More explicit way to get root
             else:
                  logger.error(f"Failed to create Mega folder '{MEGA_FOLDER_NAME}'. Uploads will go to root.")
                  mega_upload_folder_node = await asyncio.to_thread(m.get_root_node)

        if mega_upload_folder_node is None:
             logger.warning("Failed to obtain a valid Mega folder node. Uploads might fail or go to an unexpected location.")
             # Fallback one last time if needed
             mega_upload_folder_node = await asyncio.to_thread(m.get_root_node)
             logger.info(f"Falling back to root node: {mega_upload_folder_node.get('h', 'N/A')}")


        return True

    except AuthError as auth_e:
         logger.error(f"Mega.nz authentication failed: {auth_e}. Check MEGA_EMAIL and MEGA_PASSWORD.", exc_info=True)
         mega_logged_in = False
         return False
    except ApiError as api_e:
         logger.error(f"Mega.nz API error during initialization: {api_e}", exc_info=True)
         mega_logged_in = False # May or may not be logged in, assume not for safety
         return False
    except Exception as e:
        logger.error(f"Mega.nz initialization/login failed with unexpected error: {e}", exc_info=True)
        mega_logged_in = False
        return False

# --- Platform Detection ---
PLATFORM_PATTERNS = {
    "YouTube": re.compile(r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w-]+"),
    "Instagram": re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/(?:p/|reel/|stories/|tv/)[\w-]+"),
    "Facebook": re.compile(r"(?:https?://)?(?:www\.|m\.|web\.)?facebook\.com/(?:watch/?\?v=|video\.php\?v=|[^/]+/videos/|[^/]+/posts/|reel/)[\d\w.]+"),
    "Twitter/X": re.compile(r"(?:https?://)?(?:www\.)?(?:x\.com|twitter\.com)/[^/]+/status/\d+"),
    "Adult": re.compile(r"(?:https?://)?(?:www\.)?(?:pornhub\.com|xvideos\.com|redtube\.com|xhamster\.com|xnxx\.com)/.+") # Simplified
}

PLATFORM_HANDLERS = {
    "YouTube": process_youtube,
    "Instagram": process_instagram, # Default video handler
    "Facebook": process_facebook,
    "Twitter/X": download_twitter_media,
    "Adult": process_adult,
}
# Specific handler for Instagram posts/stories containing images/videos
INSTAGRAM_POST_HANDLER = process_instagram_image

def detect_platform(url: str) -> Optional[str]:
    """Detects the platform based on URL patterns."""
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    logger.warning(f"Could not detect platform for URL: {url}")
    return None

# --- Helper Functions ---
async def send_message(chat_id: int, text: str, **kwargs):
    """Sends a message asynchronously with error handling."""
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logger.error(f"Error sending message to chat {chat_id}: {e}", exc_info=True)

async def upload_to_mega(file_path: str, filename: str) -> Optional[str]:
    """
    Uploads a file to Mega.nz and returns a shareable link.
    Uses asyncio.to_thread for blocking mega.py calls.
    """
    global mega, mega_logged_in, mega_upload_folder_node
    if not mega_logged_in:
        logger.warning("Mega client not logged in. Attempting re-login before upload.")
        if not await initialize_mega():
             logger.error("Mega re-login attempt failed during upload process.")
             return None
        # Re-check login status after attempt
        if not mega_logged_in:
             logger.error("Mega login failed, cannot upload.")
             return None

    if mega is None:
        logger.error("Mega client object is None. Cannot upload.")
        return None

    if mega_upload_folder_node is None:
        logger.error("Mega upload folder node is not set. Cannot upload reliably.")
        # Optionally fallback to root again, but indicates an earlier setup issue
        # mega_upload_folder_node = await asyncio.to_thread(mega.get_root_node)
        # if mega_upload_folder_node is None: return None
        return None # Safer to fail if folder setup didn't work

    try:
        logger.info(f"Attempting to upload '{filename}' ({os.path.getsize(file_path)} bytes) to Mega.nz...")
        # Use asyncio.to_thread to run the blocking mega.py upload call
        # mega.upload() returns the node handle ('h') of the uploaded file
        dest_node_handle = await asyncio.to_thread(
            mega.upload,
            file_path,
            dest=mega_upload_folder_node.get('h') # Pass the handle 'h' of the destination folder
        )

        if not dest_node_handle:
            logger.error(f"Mega.nz upload failed for '{filename}' (returned None).")
            return None

        logger.info(f"Successfully uploaded '{filename}' (Node: {dest_node_handle}). Generating export link...")

        # Use asyncio.to_thread for the blocking export call
        # mega.export() needs the file's node handle or path on Mega
        link = await asyncio.to_thread(mega.export, dest_node_handle)

        if not link:
             logger.error(f"Failed to generate Mega.nz export link for '{filename}' (Node: {dest_node_handle}).")
             return None

        logger.info(f"Mega.nz link generated: {link}")
        return link

    except ApiError as api_e:
         logger.error(f"Mega.nz API error during upload/export for '{filename}': {api_e}", exc_info=True)
         # Consider re-login attempt or specific error handling based on ApiError details
         mega_logged_in = False # Assume session might be invalid
         return None
    except Exception as e:
        logger.error(f"Unexpected Mega.nz upload/export error for '{filename}': {e}", exc_info=True)
        # Attempt re-login in case of session issues
        mega_logged_in = False # Assume login might be invalid
        return None
    finally:
        # Optional: Check Mega client status after operation
        pass

async def process_download(message: Message, url: str, is_audio: bool = False,
                           is_video_trim: bool = False, is_audio_trim: bool = False,
                           start_time: Optional[str] = None, end_time: Optional[str] = None):
    """Handles video/audio download/trimming and sends it to Telegram or Mega.nz."""
    chat_id = message.chat.id
    request_type = "Media Download"
    if is_audio: request_type = "Audio Extraction"
    elif is_video_trim: request_type = "Video Trimming"
    elif is_audio_trim: request_type = "Audio Trimming"

    try:
        await send_message(chat_id, f"⏳ **Processing your {request_type.lower()} request...**\nURL: {url}")
        logger.info(f"Processing URL: {url}, Type: {request_type}, ChatID: {chat_id}")

        # Detect platform
        platform = detect_platform(url)
        if not platform:
            await send_message(chat_id, "⚠️ **Unsupported URL or platform.** Please send a valid link from supported sites.")
            return

        # --- Call appropriate handler ---
        file_paths: List[str] = []
        file_size: Optional[int] = None
        download_url: Optional[str] = None # Keep track of original download URL if available

        try:
            if is_video_trim:
                logger.info(f"Calling process_video_trim: Start={start_time}, End={end_time}")
                if start_time and end_time:
                    result = await process_video_trim(url, start_time, end_time)
                    if result:
                        file_path, file_size = result
                        file_paths = [file_path] if file_path else []
                else:
                     raise ValueError("Start and end times required for trimming.")

            elif is_audio_trim:
                logger.info(f"Calling process_audio_trim: Start={start_time}, End={end_time}")
                if start_time and end_time:
                    result = await process_audio_trim(url, start_time, end_time)
                    if result:
                        file_path, file_size = result
                        file_paths = [file_path] if file_path else []
                else:
                     raise ValueError("Start and end times required for trimming.")

            elif is_audio:
                logger.info("Calling extract_audio_ffmpeg...")
                result = await extract_audio_ffmpeg(url) # Expects (path, size) or just path
                if isinstance(result, tuple) and len(result) >= 1:
                    file_path = result[0]
                    file_size = result[1] if len(result) > 1 else None
                    file_paths = [file_path] if file_path else []
                elif isinstance(result, str):
                    file_paths = [result]
                    file_size = None # Need to get size later
                else:
                     logger.warning(f"Unexpected result from extract_audio_ffmpeg: {result}")


            else: # Regular Video/Media download
                logger.info(f"Handling general download for platform: {platform}")
                handler = PLATFORM_HANDLERS.get(platform)
                specific_instagram_post = False
                if platform == "Instagram":
                    # Differentiate based on URL structure for post/story vs reel/igtv
                    if "/p/" in url or "/stories/" in url:
                        logger.info("Using Instagram Post/Story handler...")
                        handler = INSTAGRAM_POST_HANDLER
                        specific_instagram_post = True # Flag to potentially handle list returns differently
                    elif "/reel/" in url or "/tv/" in url:
                         logger.info("Using Instagram Reel/IGTV handler (process_instagram)...")
                         handler = process_instagram # Explicitly use video handler
                    else: # Fallback for other instagram url types?
                         logger.info("Using default Instagram handler (process_instagram)...")
                         handler = process_instagram

                if not handler:
                    await send_message(chat_id, f"❌ **No specific handler configured for {platform}.**")
                    return

                result = await handler(url)

                # --- Process handler results carefully ---
                # Handlers might return:
                # 1. (filepath: str, size: int, source_url: Optional[str])
                # 2. (filepath: str, size: int)
                # 3. filepath: str
                # 4. List[str] (especially INSTAGRAM_POST_HANDLER)
                # 5. Tuple[List[str], Optional[int], Optional[str]] (INSTAGRAM_POST_HANDLER variant?)
                # 6. None or False on failure

                if isinstance(result, tuple):
                    if len(result) >= 3 and isinstance(result[0], (str, list)): # path(s), size, url
                        temp_paths, file_size, download_url = result[:3]
                        file_paths = temp_paths if isinstance(temp_paths, list) else [temp_paths] if temp_paths else []
                    elif len(result) == 2 and isinstance(result[0], (str, list)): # path(s), size
                        temp_paths, file_size = result
                        file_paths = temp_paths if isinstance(temp_paths, list) else [temp_paths] if temp_paths else []
                    elif len(result) == 1 and isinstance(result[0], str): # single path in a tuple
                        file_paths = [result[0]]
                    else:
                        logger.warning(f"Unexpected tuple structure from handler: {result}")
                elif isinstance(result, list): # list of paths
                     file_paths = [p for p in result if isinstance(p, str)] # Filter out non-strings
                     file_size = None # Need to calculate later per file
                elif isinstance(result, str): # single path
                    file_paths = [result] if result else []
                    file_size = None # Need to calculate later
                else:
                    logger.warning(f"Handler for {platform} returned unexpected type or None: {result}")

        except ValueError as ve: # Catch specific errors like missing trim times
             logger.error(f"Value error during handler call: {ve}", exc_info=True)
             await send_message(chat_id, f"❌ **Error:** {ve}")
             return
        except Exception as handler_error:
             logger.error(f"Error executing handler for {platform}: {handler_error}", exc_info=True)
             await send_message(chat_id, f"❌ **Failed to process media from the URL.** Error: `{handler_error}`")
             return


        logger.info(f"Handler returned: file_paths={file_paths}, file_size={file_size} (may be per file), download_url={download_url}")

        if not file_paths or all(not path for path in file_paths):
            logger.warning("No valid file paths returned from platform handler or file processing failed.")
            await send_message(chat_id, "❌ **Download failed.** No media could be retrieved or processed from the URL.")
            return

        # --- Process and Send/Upload each file ---
        success_count = 0
        fail_count = 0
        for file_path in file_paths:
            if not file_path or not isinstance(file_path, str) or not await asyncio.to_thread(os.path.exists, file_path):
                logger.warning(f"File path '{file_path}' does not exist or is invalid. Skipping.")
                fail_count += 1
                continue

            filename_base = os.path.basename(file_path)
            try:
                # Get actual file size if not provided or if multiple files
                current_file_size = file_size if len(file_paths) == 1 and file_size is not None else await asyncio.to_thread(os.path.getsize, file_path)

                # --- Check size and decide destination ---
                if current_file_size > MEGA_UPLOAD_THRESHOLD:
                    logger.info(f"File '{filename_base}' ({current_file_size} bytes) > threshold. Uploading to Mega.nz.")

                    mega_link = await upload_to_mega(file_path, filename_base)

                    if mega_link:
                        logger.info(f"Successfully uploaded '{filename_base}' to Mega.nz: {mega_link}")
                        await send_message(
                            chat_id,
                            f"✅ **File too large for Telegram.**\n'{filename_base}'\n"
                            f"📥 [Download from Mega.nz]({mega_link})",
                            parse_mode="Markdown",
                            disable_web_page_preview=True
                        )
                        success_count += 1
                    else:
                        logger.warning(f"Mega.nz upload failed for '{filename_base}'")
                        fail_count += 1
                        # Fallback to original download URL if available and upload failed
                        if download_url:
                             await send_message(
                                  chat_id,
                                  f"⚠️ **File '{filename_base}' too large & Mega upload failed.**\n"
                                  f"📥 [Try Original Source Link]({download_url}) (If available)",
                                  parse_mode="Markdown",
                                  disable_web_page_preview=True
                             )
                        else:
                             await send_message(chat_id, f"❌ **File '{filename_base}' is too large and failed to upload to Mega.nz.**")

                else: # File size is okay for Telegram
                    logger.info(f"File '{filename_base}' ({current_file_size} bytes) OK for Telegram. Sending...")
                    try:
                        # Use aiofiles for async read
                        async with aiofiles.open(file_path, "rb") as file:
                            # Determine send method based on flags or extension
                            if is_audio or is_audio_trim or filename_base.lower().endswith(('.mp3', '.m4a', '.ogg', '.flac', '.wav', '.aac')):
                                await bot.send_audio(chat_id, file, timeout=600, caption=filename_base)
                            elif filename_base.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')):
                                 await bot.send_photo(chat_id, file, timeout=180, caption=filename_base)
                            elif filename_base.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
                                await bot.send_video(chat_id, file, supports_streaming=True, timeout=600, caption=filename_base)
                            else: # Send as document for unknown types
                                logger.warning(f"Unknown file type '{filename_base}', sending as document.")
                                await bot.send_document(chat_id, file, timeout=600, caption=filename_base)
                        logger.info(f"Successfully sent '{filename_base}' to Telegram.")
                        success_count += 1

                    except Exception as send_error:
                        logger.error(f"Error sending file '{filename_base}' to Telegram: {send_error}", exc_info=True)
                        fail_count += 1
                        # Handle Telegram specific "Too Large" error (413) even if initial check passed
                        if "413" in str(send_error) or "too large" in str(send_error).lower():
                            logger.warning(f"Telegram reported file '{filename_base}' too large on send attempt (413), attempting Mega.nz upload.")
                            mega_link = await upload_to_mega(file_path, filename_base)
                            if mega_link:
                                await send_message(
                                    chat_id,
                                    f"✅ **File too large for Telegram (on send).**\n'{filename_base}'\n"
                                    f"📥 [Download from Mega.nz]({mega_link})",
                                    parse_mode="Markdown",
                                    disable_web_page_preview=True
                                )
                                success_count += 1 # Count as success via Mega
                                fail_count -= 1 # Correct the count
                            else:
                                await send_message(chat_id, f"❌ **File '{filename_base}' too large for Telegram and Mega.nz upload failed.**")
                        else:
                            # Send specific error message to user
                            await send_message(chat_id, f"❌ **Error sending file '{filename_base}':** `{str(send_error)}`")

            finally:
                # --- Cleanup the local file ---
                try:
                    # Ensure file exists before removing
                    if await asyncio.to_thread(os.path.exists, file_path):
                        await asyncio.to_thread(os.remove, file_path)
                        logger.info(f"Cleaned up temp file: {file_path}")
                    else:
                         logger.info(f"Temp file already removed or not found: {file_path}")
                except OSError as cleanup_error:
                    logger.error(f"Failed to clean up file '{file_path}': {cleanup_error}", exc_info=True)
                except Exception as generic_cleanup_error:
                     logger.error(f"Unexpected error cleaning up file '{file_path}': {generic_cleanup_error}", exc_info=True)


        # --- Final Status Message ---
        if success_count > 0 and fail_count == 0:
             await send_message(chat_id, f"✅ **Successfully processed {success_count} file(s)!**")
        elif success_count > 0 and fail_count > 0:
             await send_message(chat_id, f"⚠️ **Processed {success_count} file(s) successfully, but {fail_count} failed.**")
        elif success_count == 0 and fail_count > 0:
             await send_message(chat_id, f"❌ **Failed to process {fail_count} file(s) from the URL.**")
        # If success=0, fail=0, it means no files were found initially (handled earlier)

        gc.collect() # Request garbage collection

    except Exception as e:
        logger.error(f"Unhandled error in process_download for URL {url}: {e}", exc_info=True)
        await send_message(chat_id, f"❌ **An unexpected error occurred processing your request.** Please try again later or report the issue if it persists.")
        # Also cleanup any potential leftover file if path is known (less likely here)
        # try: ... os.remove ... except: pass


# NOTE: process_image_download is merged into process_download logic
# The general process_download now checks for Instagram /p/ or /stories/
# and uses the INSTAGRAM_POST_HANDLER which should handle images/videos from posts.
# The explicit /image command handler below will still queue the task correctly.


async def worker():
    """Worker function for parallel processing of downloads from the queue."""
    # Ensure Mega is initialized within the worker's loop context if needed,
    # but the global initialization in main() should handle the first time.
    if not mega_logged_in:
        logger.info("Worker started, ensuring Mega client is initialized...")
        await initialize_mega() # Ensure it's ready before processing tasks

    while True:
        task = await download_queue.get()
        task_info_str = "Unknown task type"
        try:
            if isinstance(task, tuple):
                 message = task[0]
                 if isinstance(message, Message) and hasattr(message, 'text'):
                      task_info_str = f"ChatID: {message.chat.id}, Text: {message.text[:50]}..."
                 else:
                     task_info_str = f"Task tuple starting with: {type(message)}"

            logger.info(f"Worker processing task: {task_info_str}")

            # --- Task Dispatch Logic ---
            # Structure 1: (message, url) -> Implicitly from /image command handler
            # Structure 2: (message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time) -> From other commands or general URL
            # Structure 3: Add more specific structures if needed (e.g., dedicated object)

            if isinstance(task, tuple) and len(task) == 2 and isinstance(task[0], Message) and isinstance(task[1], str):
                 # This structure comes ONLY from the /image command handler now.
                 # Treat it as a general download, letting process_download pick the right handler.
                 message, url = task
                 logger.info(f"Dispatching task (type /image) to process_download for URL: {url}")
                 await process_download(message, url) # Let process_download handle platform detection

            elif isinstance(task, tuple) and len(task) == 7 and isinstance(task[0], Message):
                 # Standard download/trim task
                 message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time = task
                 logger.info(f"Dispatching task (type general/audio/trim) to process_download for URL: {url}")
                 await process_download(message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time)
            else:
                 logger.warning(f"Worker received unknown or malformed task format: {task}")
                 if isinstance(task, tuple) and len(task)>0 and isinstance(task[0], Message):
                      await send_message(task[0].chat.id, "❌ Internal error: Received malformed task.")


        except Exception as worker_error:
             logger.error(f"Error occurred processing task in worker: {worker_error}", exc_info=True)
             # Try to inform the user if possible
             if isinstance(task, tuple) and len(task)>0 and isinstance(task[0], Message):
                  await send_message(task[0].chat.id, f"❌ An internal error occurred processing your request. Please try again.")

        finally:
             download_queue.task_done()
             logger.debug("Worker finished task, calling task_done()")
             gc.collect() # Run garbage collection after each task


# --- Telegram Bot Handlers ---

@bot.message_handler(commands=["start", "help"])
async def send_welcome(message: Message):
    """Sends welcome message with bot instructions."""
    welcome_text = (
        "🤖 **Media Download Bot** 🤖\n\n"
        "I can help you download media from various platforms.\n\n"
        "➡️ **How to Use:**\n"
        "1. Just send me the URL of the media!\n"
        "2. For large files (>~48MB), I'll upload to Mega.nz and give you a link.\n\n"
        "⚙️ **Specific Commands:**\n"
        "`/audio <URL>` - Extract full audio from video\n"
        "`/image <URL>` - Download images/videos from an Instagram post/story URL\n"
        "`/trim <URL> HH:MM:SS HH:MM:SS` - Trim video\n"
        "`/trimAudio <URL> HH:MM:SS HH:MM:SS` - Trim audio\n\n"
        "✂️ **Trim Examples:**\n"
        "`/trim https://youtu.be/xxxx 00:00:30 00:01:15`\n"
        "`/trimAudio https://facebook.com/watch/xxxx 0:10:05 0:12:00`\n\n"
        "**Supported Sites (Examples):**\n"
        "- YouTube (Videos, Shorts)\n"
        "- Instagram (Posts, Stories, Reels, IGTV)\n"
        "- Facebook (Videos, Reels)\n"
        "- Twitter/X (Videos, GIFs)\n"
        # "- Pornhub, XVideos, etc. (Use responsibly)\n\n" # Optionally uncomment
        "\n_Note: Support for sites depends on external libraries and may change._"
    )
    # Use Markdown for better formatting
    await send_message(message.chat.id, welcome_text, parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=["audio"])
async def handle_audio_request(message: Message):
    """Handles /audio command."""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await send_message(message.chat.id, "⚠️ Please provide a URL after `/audio`.\nExample: `/audio https://youtu.be/VIDEO_ID`")
        return
    url = parts[1].strip()
    if not re.match(r"https?://", url):
         await send_message(message.chat.id, "⚠️ Invalid URL provided.")
         return

    # Use the 7-tuple format for the queue
    await download_queue.put((message, url, True, False, False, None, None))
    await send_message(message.chat.id, "🎵 Added URL to audio extraction queue!")

@bot.message_handler(commands=["image"])
async def handle_image_request(message: Message):
    """Handles /image command (specifically for Instagram posts/stories)."""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await send_message(message.chat.id, "⚠️ Please provide an Instagram URL after `/image`.\nExample: `/image https://instagram.com/p/abc...`")
        return
    url = parts[1].strip()

    # Check if URL is Instagram (basic check)
    if not PLATFORM_PATTERNS["Instagram"].search(url):
        await send_message(message.chat.id, "⚠️ **This command currently only supports Instagram post/story URLs.** For other videos/reels, just send the URL directly.")
        return

    # Add to download queue using the simplified 2-tuple format, recognized by the worker
    await download_queue.put((message, url))
    await send_message(message.chat.id, "🖼️ Added Instagram post/story URL to the download queue!")


@bot.message_handler(commands=["trim"])
async def handle_video_trim_request(message: Message):
    """Handles /trim command for video."""
    # Regex to capture URL and two timestamps (HH:MM:SS or M:SS)
    match = re.search(r"/trim\s+(https?://[^\s]+)\s+([\d:]+)\s+([\d:]+)", message.text, re.IGNORECASE)
    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format. Use:\n`/trim <URL> <StartTime> <EndTime>`\n"
            "Timestamps like HH:MM:SS or M:SS (e.g., `0:10` `1:15:30`)\n"
            "Example: `/trim https://... 00:00:10 00:00:55`",
             parse_mode="Markdown"
        )
        return

    url, start_time, end_time = match.groups()
    # Basic validation could be added here for timestamp format if needed
    # Use the 7-tuple format for the queue
    await download_queue.put((message, url, False, True, False, start_time, end_time))
    await send_message(message.chat.id, "✂️🎬 Added video trimming task to the queue!")

@bot.message_handler(commands=["trimAudio"])
async def handle_audio_trim_request(message: Message):
    """Handles /trimAudio command."""
    match = re.search(r"/trimAudio\s+(https?://[^\s]+)\s+([\d:]+)\s+([\d:]+)", message.text, re.IGNORECASE)
    if not match:
        await send_message(
            message.chat.id,
             "⚠️ Invalid format. Use:\n`/trimAudio <URL> <StartTime> <EndTime>`\n"
             "Timestamps like HH:MM:SS or M:SS (e.g., `0:10` `1:15:30`)\n"
             "Example: `/trimAudio https://... 00:01:00 00:01:30`",
             parse_mode="Markdown"
        )
        return

    url, start_time, end_time = match.groups()
    # Basic validation could be added here
    # Use the 7-tuple format for the queue
    await download_queue.put((message, url, False, False, True, start_time, end_time))
    await send_message(message.chat.id, "✂️🎵 Added audio trimming task to the queue!")

# General message handler for URLs (must be last text handler)
@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message: Message):
    """Handles general text messages, assuming they are URLs for download."""
    # Ignore commands handled by specific handlers
    if message.text.startswith('/'):
        # Optional: Send a message indicating unknown command
        # await send_message(message.chat.id, f"❓ Unknown command: `{message.text.split()[0]}`. Send /help for instructions.")
        logger.info(f"Ignoring unknown command message from {message.chat.id}: {message.text}")
        return

    url = message.text.strip()
    # Basic URL validation
    if not re.match(r"https?://\S+", url): # Check for http(s):// followed by non-space chars
         # Avoid sending error for casual chat messages
         # await send_message(message.chat.id, "🤔 That doesn't look like a valid URL I can process. Please send a direct link to the media.")
         logger.info(f"Ignoring non-URL message from {message.chat.id}: {message.text[:100]}")
         return

    # Add general URLs to the download queue using the 7-tuple format
    await download_queue.put((message, url, False, False, False, None, None))
    logger.info(f"Added general URL from {message.chat.id} to queue: {url}")
    await send_message(message.chat.id, "🔗 Added URL to the download queue!")


# --- Main Execution ---
async def main():
    """Initializes Mega, starts workers, and runs the bot polling."""
    logger.info("--- Bot Starting Up ---")
    # Initialize Mega.nz client first
    if not await initialize_mega():
        logger.critical("Failed to initialize Mega.nz client on startup.")
        # Decide if the bot should run without Mega uploads
        # For now, we allow it but log a critical warning. Uploads > threshold will fail.
        logger.warning("Bot will continue running, but uploads to Mega.nz will likely fail.")
        # uncomment return to exit if Mega is essential
        # return

    # Start worker tasks
    num_workers = min(4, (os.cpu_count() or 1) + 1) # Start a few workers
    logger.info(f"Starting {num_workers} download worker tasks...")
    worker_tasks = []
    for i in range(num_workers):
        task = asyncio.create_task(worker(), name=f"Worker-{i+1}")
        worker_tasks.append(task)
        logger.info(f"Worker {i+1} task created.")

    # Start polling
    logger.info("Starting Telegram bot polling...")
    stop_event = asyncio.Event()

    try:
        # Run polling in a way that allows graceful shutdown
        await bot.polling(non_stop=True, timeout=30, logger_level=logging.INFO, none_stop=True)
        # Note: infinity_polling is simpler but harder to stop gracefully sometimes.
        # await bot.infinity_polling(timeout=30, logger_level=logging.INFO) # Alternative

        # Keep main running until interrupted (infinity_polling does this internally)
        # await stop_event.wait() # Use this if not using non_stop/infinity_polling

    except asyncio.CancelledError:
        logger.info("Polling task cancelled.")
    except Exception as e:
        logger.critical(f"Bot polling loop encountered a critical error: {e}", exc_info=True)
    finally:
        logger.info("--- Bot Shutting Down ---")
        # Stop polling (if applicable, bot.stop_polling() might be needed depending on method)
        # bot.stop_polling() # Uncomment if using a polling method that needs explicit stop

        # Gracefully cancel worker tasks
        logger.info("Cancelling worker tasks...")
        for i, task in enumerate(worker_tasks):
             task.cancel()
             logger.info(f"Cancel requested for Worker {i+1}")

        # Wait for workers to finish cancelling
        results = await asyncio.gather(*worker_tasks, return_exceptions=True)
        for i, res in enumerate(results):
             if isinstance(res, asyncio.CancelledError):
                  logger.info(f"Worker {i+1} cancelled successfully.")
             elif isinstance(res, Exception):
                  logger.error(f"Worker {i+1} finished with error during shutdown: {res}", exc_info=res)
             else:
                  logger.info(f"Worker {i+1} finished normally during shutdown.") # Should not happen if cancelled

        logger.info("Workers cancellation process complete.")

        # Perform mega logout if necessary (optional, mega.py might handle sessions)
        # global mega, mega_logged_in
        # if mega_logged_in and mega:
        #     try:
        #         logger.info("Attempting Mega.nz logout...")
        #         # Check if mega.py has an explicit logout method
        #         # await asyncio.to_thread(mega.logout) # If it exists and is blocking
        #         logger.info("Mega.nz session likely closed on exit.")
        #     except Exception as logout_err:
        #         logger.error(f"Error during Mega logout attempt: {logout_err}", exc_info=True)

        logger.info("Bot shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually (KeyboardInterrupt).")
    except Exception as main_err:
         logger.critical(f"Critical error in main execution block: {main_err}", exc_info=True)
