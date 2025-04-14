# -*- coding: utf-8 -*- # Recommended for wider compatibility

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
try:
    # ADDED: Explicit import for specific Mega exceptions (adjust path if needed)
    from mega.errors import AuthError, ApiError
except ImportError:
    # Fallback if specific errors aren't directly available (less ideal)
    AuthError = Exception # Or a more specific base if known
    ApiError = Exception
    print("WARN: Could not import specific AuthError/ApiError from mega.errors. Using broader Exception.")


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
    from handlers.instagram_handler import process_instagram
    from handlers.image_handlers import process_instagram_image
    from handlers.facebook_handlers import process_facebook
    from handlers.common_handler import process_adult
    from handlers.x_handler import download_twitter_media
    from handlers.trim_handlers import process_video_trim, process_audio_trim
    # REMOVED: Duplicate import of process_instagram_image
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

    # ADDED: Check if credentials are set before attempting login
    if not MEGA_EMAIL or not MEGA_PASSWORD:
        logger.error("Mega Email/Password not set in config. Bot cannot use Mega.nz features.")
        return False

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

        # This complex check handles variations in mega.py's find() return value
        if folder_node_tuple and isinstance(folder_node_tuple, tuple) and len(folder_node_tuple) > 0:
             # Assumes structure like ((node_dict, type),)
             if isinstance(folder_node_tuple[0], tuple) and len(folder_node_tuple[0]) > 0 and isinstance(folder_node_tuple[0][0], dict):
                  mega_upload_folder_node = folder_node_tuple[0][0] # Get the node dictionary
                  logger.info(f"Found Mega folder node: {mega_upload_folder_node.get('h', 'N/A')}") # Log handle 'h'
             # Fallback if the structure is different (e.g., (node_dict, type))
             elif isinstance(folder_node_tuple[0], dict):
                  mega_upload_folder_node = folder_node_tuple[0]
                  logger.info(f"Found Mega folder node (alternative structure): {mega_upload_folder_node.get('h', 'N/A')}")
             else:
                 logger.warning(f"Found Mega item '{MEGA_FOLDER_NAME}', but structure is unexpected: {folder_node_tuple}. Trying creation...")
                 folder_node_tuple = None # Force creation attempt

        if not mega_upload_folder_node: # Covers case where it wasn't found or structure was wrong
             logger.info(f"Mega folder '{MEGA_FOLDER_NAME}' not found or structure unexpected. Creating...")
             # Run blocking create folder in a separate thread
             created_folder_list = await asyncio.to_thread(m.create_folder, MEGA_FOLDER_NAME) # returns a list like [{...}]

             if created_folder_list and isinstance(created_folder_list, list) and len(created_folder_list) > 0 and isinstance(created_folder_list[0], dict):
                 logger.info(f"Mega folder '{MEGA_FOLDER_NAME}' created.")
                 # Find it again to get the node, hopefully in a consistent format now
                 folder_node_tuple_retry = await asyncio.to_thread(m.find, MEGA_FOLDER_NAME, exclude_deleted=True)
                 if folder_node_tuple_retry and isinstance(folder_node_tuple_retry[0], tuple) and len(folder_node_tuple_retry[0]) > 0 and isinstance(folder_node_tuple_retry[0][0], dict):
                      mega_upload_folder_node = folder_node_tuple_retry[0][0]
                      logger.info(f"Using newly created Mega folder node: {mega_upload_folder_node.get('h', 'N/A')}")
                 elif folder_node_tuple_retry and isinstance(folder_node_tuple_retry[0], dict): # Alternative structure check
                      mega_upload_folder_node = folder_node_tuple_retry[0]
                      logger.info(f"Using newly created Mega folder node (alternative structure): {mega_upload_folder_node.get('h', 'N/A')}")
                 else:
                     logger.error(f"Failed to find created Mega folder '{MEGA_FOLDER_NAME}' after creation. Uploads will go to root.")
                     mega_upload_folder_node = await asyncio.to_thread(m.get_root_node)
             else:
                  logger.error(f"Failed to create Mega folder '{MEGA_FOLDER_NAME}'. Uploads will go to root.")
                  mega_upload_folder_node = await asyncio.to_thread(m.get_root_node)

        # Final fallback if node is still None
        if mega_upload_folder_node is None:
             logger.warning("Failed to obtain a valid Mega folder node. Uploads might fail or go to an unexpected location.")
             mega_upload_folder_node = await asyncio.to_thread(m.get_root_node)
             logger.info(f"Falling back to root node: {mega_upload_folder_node.get('h', 'N/A') if mega_upload_folder_node else 'N/A'}")

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
    "Instagram": re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/(?:p/|reel/|stories/|tv/)[\w-]+/?"), # Added optional trailing slash
    "Facebook": re.compile(r"(?:https?://)?(?:www\.|m\.|web\.)?facebook\.com/(?:watch/?\?v=|video\.php\?v=|[^/]+/videos/|[^/]+/posts/|reel/)[\d\w.]+/?"), # Added optional trailing slash
    "Twitter/X": re.compile(r"(?:https?://)?(?:www\.)?(?:x\.com|twitter\.com)/[^/]+/status/\d+"),
    "Adult": re.compile(r"(?:https?://)?(?:www\.)?(?:pornhub\.com|xvideos\.com|redtube\.com|xhamster\.com|xnxx\.com)/.+", re.IGNORECASE) # Added case-insensitivity
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
            logger.info(f"Detected platform '{platform}' for URL: {url}")
            return platform
    logger.warning(f"Could not detect platform for URL: {url}")
    return None

# --- Helper Functions ---
async def send_message(chat_id: int, text: str, **kwargs):
    """Sends a message asynchronously with error handling."""
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        # Avoid logging errors for potentially common issues like bot blocked by user
        if "bot was blocked by the user" in str(e).lower():
             logger.warning(f"Bot blocked by user in chat {chat_id}.")
        elif "chat not found" in str(e).lower():
             logger.warning(f"Chat not found: {chat_id}.")
        else:
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
        return None # Safer to fail if folder setup didn't work

    try:
        # CHANGED: Use asyncio.to_thread for blocking os.path.getsize
        file_size_bytes = await asyncio.to_thread(os.path.getsize, file_path)
        logger.info(f"Attempting to upload '{filename}' ({file_size_bytes} bytes) to Mega.nz...")

        # Use asyncio.to_thread to run the blocking mega.py upload call
        # Pass the handle 'h' of the destination folder
        dest_folder_handle = mega_upload_folder_node.get('h')
        if not dest_folder_handle:
            logger.error(f"Mega destination folder node has no handle ('h'). Cannot upload '{filename}'. Node: {mega_upload_folder_node}")
            return None

        uploaded_file_node = await asyncio.to_thread(
            mega.upload,
            file_path,
            dest=dest_folder_handle
        )

        if not uploaded_file_node:
            logger.error(f"Mega.nz upload failed for '{filename}' (returned None).")
            return None

        # mega.upload typically returns the node *handle* ('h') directly, not the full node dict
        # Let's assume uploaded_file_node is the handle string 'h'
        logger.info(f"Successfully uploaded '{filename}' (Node handle: {uploaded_file_node}). Generating export link...")

        # Use asyncio.to_thread for the blocking export call
        # mega.export() needs the file's node handle or path on Mega
        link = await asyncio.to_thread(mega.export, uploaded_file_node)

        if not link:
             logger.error(f"Failed to generate Mega.nz export link for '{filename}' (Node handle: {uploaded_file_node}).")
             return None

        logger.info(f"Mega.nz link generated: {link}")
        return link

    except FileNotFoundError:
        logger.error(f"File not found for Mega upload: {file_path}")
        return None
    except AuthError as auth_e: # More specific catch
         logger.error(f"Mega.nz authentication error during upload/export for '{filename}': {auth_e}", exc_info=True)
         mega_logged_in = False # Assume session might be invalid
         return None
    except ApiError as api_e:
         logger.error(f"Mega.nz API error during upload/export for '{filename}': {api_e}", exc_info=True)
         # Consider re-login attempt or specific error handling based on ApiError details
         # For now, assume session might be invalid
         mega_logged_in = False
         return None
    except Exception as e:
        logger.error(f"Unexpected Mega.nz upload/export error for '{filename}': {e}", exc_info=True)
        # Attempt re-login in case of session issues? Maybe too aggressive.
        mega_logged_in = False # Assume login might be invalid
        return None

async def process_download(message: Message, url: str, is_audio: bool = False,
                           is_video_trim: bool = False, is_audio_trim: bool = False,
                           start_time: Optional[str] = None, end_time: Optional[str] = None):
    """Handles video/audio download/trimming and sends it to Telegram or Mega.nz."""
    chat_id = message.chat.id
    request_type = "Media Download"
    if is_audio: request_type = "Audio Extraction"
    elif is_video_trim: request_type = "Video Trimming"
    elif is_audio_trim: request_type = "Audio Trimming"

    processing_msg = None
    try:
        # Send initial message and store it to potentially edit later
        processing_msg = await bot.send_message(chat_id, f"⏳ **Processing your {request_type.lower()} request...**\nURL: `{url}`")
        logger.info(f"Processing URL: {url}, Type: {request_type}, ChatID: {chat_id}")

        # Detect platform
        platform = detect_platform(url)
        if not platform:
            await bot.edit_message_text("⚠️ **Unsupported URL or platform.** Please send a valid link from supported sites.", chat_id, processing_msg.message_id)
            return

        # --- Call appropriate handler ---
        file_paths: List[str] = []
        # IDEA: Use a dataclass or NamedTuple for handler results for clarity
        # from collections import namedtuple
        # MediaResult = namedtuple("MediaResult", ["paths", "size", "source_url"])
        handler_result: Any = None # Placeholder for result

        try:
            await bot.edit_message_text(f"⏳ **Detected {platform}. Calling handler...**\nURL: `{url}`", chat_id, processing_msg.message_id)

            if is_video_trim:
                logger.info(f"Calling process_video_trim: Start={start_time}, End={end_time}")
                if start_time and end_time:
                    handler_result = await process_video_trim(url, start_time, end_time)
                else:
                     raise ValueError("Start and end times required for trimming.")

            elif is_audio_trim:
                logger.info(f"Calling process_audio_trim: Start={start_time}, End={end_time}")
                if start_time and end_time:
                    handler_result = await process_audio_trim(url, start_time, end_time)
                else:
                     raise ValueError("Start and end times required for trimming.")

            elif is_audio:
                logger.info("Calling extract_audio_ffmpeg...")
                handler_result = await extract_audio_ffmpeg(url)

            else: # Regular Video/Media download
                logger.info(f"Handling general download for platform: {platform}")
                handler = PLATFORM_HANDLERS.get(platform)
                if platform == "Instagram":
                    if "/p/" in url or "/stories/" in url:
                        logger.info("Using Instagram Post/Story handler...")
                        handler = INSTAGRAM_POST_HANDLER
                    elif "/reel/" in url or "/tv/" in url:
                         logger.info("Using Instagram Reel/IGTV handler (process_instagram)...")
                         handler = process_instagram
                    else:
                         logger.info("Using default Instagram handler (process_instagram)...")
                         handler = process_instagram

                if not handler:
                    await bot.edit_message_text(f"❌ **No specific handler configured for {platform}.**", chat_id, processing_msg.message_id)
                    return

                handler_result = await handler(url)

        except ValueError as ve: # Catch specific errors like missing trim times
             logger.error(f"Value error during handler call: {ve}", exc_info=True)
             await bot.edit_message_text(f"❌ **Error:** {ve}", chat_id, processing_msg.message_id)
             return
        except Exception as handler_error:
             logger.error(f"Error executing handler for {platform}: {handler_error}", exc_info=True)
             await bot.edit_message_text(f"❌ **Failed to process media from the URL.**\nError: `{handler_error}`", chat_id, processing_msg.message_id)
             return

        # --- Process handler results carefully (Consider standardizing handler returns) ---
        file_paths = []
        file_size: Optional[int] = None # Overall size if single file from handler
        download_url: Optional[str] = None # Original source URL if provided

        if isinstance(handler_result, tuple):
            if len(handler_result) >= 1:
                paths_data = handler_result[0]
                file_paths = paths_data if isinstance(paths_data, list) else [paths_data] if isinstance(paths_data, str) else []
                if len(handler_result) >= 2 and isinstance(handler_result[1], int):
                    file_size = handler_result[1]
                if len(handler_result) >= 3 and isinstance(handler_result[2], str):
                    download_url = handler_result[2]
            else:
                 logger.warning(f"Handler returned empty tuple: {handler_result}")
        elif isinstance(handler_result, list):
            file_paths = [p for p in handler_result if isinstance(p, str)]
        elif isinstance(handler_result, str):
            file_paths = [handler_result] if handler_result else []
        else:
            logger.warning(f"Handler for {platform} returned unexpected type or None: {handler_result}")

        # Filter out any non-existent paths just in case
        valid_paths = []
        for p in file_paths:
             if p and isinstance(p, str) and await asyncio.to_thread(os.path.exists, p):
                 valid_paths.append(p)
             else:
                 logger.warning(f"File path '{p}' from handler is invalid or does not exist. Skipping.")
        file_paths = valid_paths


        logger.info(f"Handler returned: file_paths={file_paths}, file_size={file_size} (may be total/first), download_url={download_url}")

        if not file_paths:
            logger.warning("No valid file paths returned from handler or file processing failed.")
            await bot.edit_message_text("❌ **Download failed.** No media could be retrieved or processed from the URL.", chat_id, processing_msg.message_id)
            return

        # --- Process and Send/Upload each file ---
        success_count = 0
        fail_count = 0
        total_files = len(file_paths)
        # Update status message
        await bot.edit_message_text(f"⏳ **Downloaded {total_files} file(s). Preparing to send/upload...**", chat_id, processing_msg.message_id)

        for i, file_path in enumerate(file_paths):
            filename_base = os.path.basename(file_path)
            status_prefix = f"({i+1}/{total_files}) '{filename_base}'"

            # Ensure file exists before processing (might have been deleted between check and now)
            if not await asyncio.to_thread(os.path.exists, file_path):
                logger.warning(f"File path '{file_path}' disappeared before processing. Skipping.")
                fail_count += 1
                continue

            try:
                # CHANGED: Use asyncio.to_thread for blocking os.path.getsize
                current_file_size = await asyncio.to_thread(os.path.getsize, file_path)

                # --- Check size and decide destination ---
                if current_file_size > MEGA_UPLOAD_THRESHOLD:
                    logger.info(f"File '{filename_base}' ({current_file_size} bytes) > threshold. Uploading to Mega.nz.")
                    await bot.edit_message_text(f"⏳ {status_prefix}: File large, uploading to Mega.nz...", chat_id, processing_msg.message_id, disable_web_page_preview=True)

                    # Ensure Mega is ready before upload attempt
                    if not mega_logged_in:
                         logger.warning("Mega not logged in, attempting init before upload...")
                         await initialize_mega() # Try to init/login again
                         if not mega_logged_in:
                              raise Exception("Mega login required but failed.") # Force failure if still not logged in


                    mega_link = await upload_to_mega(file_path, filename_base)

                    if mega_link:
                        logger.info(f"Successfully uploaded '{filename_base}' to Mega.nz: {mega_link}")
                        # Send Mega link as a separate message
                        await send_message(
                            chat_id,
                            f"✅ {status_prefix}: **Uploaded to Mega.nz**\n"
                            f"📥 [Download Link]({mega_link})",
                            parse_mode="Markdown",
                            disable_web_page_preview=True
                        )
                        success_count += 1
                    else:
                        logger.warning(f"Mega.nz upload failed for '{filename_base}'")
                        fail_count += 1
                        # Send failure message
                        await send_message(
                              chat_id,
                              f"❌ {status_prefix}: **File too large & Mega upload failed.**",
                              disable_web_page_preview=True
                         )
                        # Option: Provide original link if available
                        # if download_url: await send_message(...)

                else: # File size is okay for Telegram
                    logger.info(f"File '{filename_base}' ({current_file_size} bytes) OK for Telegram. Sending...")
                    await bot.edit_message_text(f"⏳ {status_prefix}: Sending via Telegram...", chat_id, processing_msg.message_id, disable_web_page_preview=True)
                    try:
                        # Use aiofiles for async read
                        async with aiofiles.open(file_path, "rb") as file:
                            # Determine send method based on flags or extension
                            sent_message = None
                            file_caption = filename_base # Keep caption simple initially
                            # Add platform/source info if available?
                            # if platform: file_caption += f"\nSource: {platform}"

                            if is_audio or is_audio_trim or filename_base.lower().endswith(('.mp3', '.m4a', '.ogg', '.flac', '.wav', '.aac')):
                                sent_message = await bot.send_audio(chat_id, file, timeout=600, caption=file_caption)
                            elif filename_base.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp')): # Removed gif - send as animation/doc?
                                 sent_message = await bot.send_photo(chat_id, file, timeout=180, caption=file_caption)
                            elif filename_base.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
                                sent_message = await bot.send_video(chat_id, file, supports_streaming=True, timeout=600, caption=file_caption)
                            elif filename_base.lower().endswith(('.gif',)):
                                sent_message = await bot.send_animation(chat_id, file, timeout=180, caption=file_caption)
                            else: # Send as document for unknown types
                                logger.warning(f"Unknown file type '{filename_base}', sending as document.")
                                sent_message = await bot.send_document(chat_id, file, timeout=600, caption=file_caption)

                        if sent_message: # Check if send call was successful
                            logger.info(f"Successfully sent '{filename_base}' to Telegram.")
                            success_count += 1
                        else:
                             # This case might not happen if exceptions are raised, but good to have
                             logger.error(f"Telegram send function returned None for '{filename_base}'. Assuming failure.")
                             fail_count += 1
                             await send_message(chat_id, f"❌ {status_prefix}: Failed to send via Telegram (unknown reason).")


                    except Exception as send_error:
                        logger.error(f"Error sending file '{filename_base}' to Telegram: {send_error}", exc_info=True)
                        fail_count += 1
                        error_str = str(send_error).lower()
                        # Handle Telegram specific "Too Large" error (413 Request Entity Too Large)
                        # or other size-related errors more broadly
                        if "too large" in error_str or "request entity too large" in error_str or "file_size" in error_str:
                            logger.warning(f"Telegram reported file '{filename_base}' too large on send attempt ({send_error}), attempting Mega.nz upload.")
                            await bot.edit_message_text(f"⏳ {status_prefix}: Telegram rejected size, trying Mega.nz...", chat_id, processing_msg.message_id, disable_web_page_preview=True)

                            # Ensure Mega is ready before upload attempt
                            if not mega_logged_in:
                                logger.warning("Mega not logged in, attempting init before upload...")
                                await initialize_mega()
                                if not mega_logged_in:
                                    await send_message(chat_id, f"❌ {status_prefix}: **File too large for Telegram & Mega login failed.**")
                                    continue # Skip to next file

                            mega_link = await upload_to_mega(file_path, filename_base)
                            if mega_link:
                                await send_message(
                                    chat_id,
                                    f"✅ {status_prefix}: **Uploaded to Mega.nz (was too large for Telegram)**\n"
                                    f"📥 [Download Link]({mega_link})",
                                    parse_mode="Markdown",
                                    disable_web_page_preview=True
                                )
                                success_count += 1 # Count as success via Mega
                                fail_count -= 1 # Correct the count
                            else:
                                await send_message(chat_id, f"❌ {status_prefix}: **File too large for Telegram and Mega.nz upload also failed.**")
                        else:
                            # Send specific error message to user for other send errors
                            await send_message(chat_id, f"❌ {status_prefix}: **Error sending via Telegram:** `{str(send_error)}`")

            except Exception as outer_process_err:
                 # Catch errors during size check or outer logic for this file
                 logger.error(f"Error processing file '{filename_base}': {outer_process_err}", exc_info=True)
                 fail_count += 1
                 await send_message(chat_id, f"❌ {status_prefix}: **An internal error occurred processing this file.**")

            finally:
                # --- Cleanup the local file ---
                try:
                    # Ensure file exists before removing
                    # CHANGED: Use asyncio.to_thread for blocking os.path.exists and os.remove
                    if await asyncio.to_thread(os.path.exists, file_path):
                        await asyncio.to_thread(os.remove, file_path)
                        logger.info(f"Cleaned up temp file: {file_path}")
                    else:
                         logger.info(f"Temp file already removed or not found (before cleanup): {file_path}")
                except OSError as cleanup_error:
                    logger.error(f"Failed to clean up file '{file_path}': {cleanup_error}", exc_info=True)
                except Exception as generic_cleanup_error:
                     logger.error(f"Unexpected error cleaning up file '{file_path}': {generic_cleanup_error}", exc_info=True)


        # --- Final Status Message ---
        # Delete the "Processing..." message now that we're done or use it for the final status
        final_message = ""
        if success_count > 0 and fail_count == 0:
             final_message = f"✅ **Successfully processed {success_count} file(s)!**"
        elif success_count > 0 and fail_count > 0:
             final_message = f"⚠️ **Processed {success_count} file(s) successfully, but {fail_count} failed.**"
        elif success_count == 0 and fail_count > 0:
             final_message = f"❌ **Failed to process {fail_count} file(s) from the URL.** See previous messages for details."
        # If success=0, fail=0, it means no files were found initially (handled earlier)

        if final_message:
            try:
                await bot.edit_message_text(final_message, chat_id, processing_msg.message_id, disable_web_page_preview=True)
            except Exception: # If editing fails (e.g., message too old), send a new one
                await send_message(chat_id, final_message)
        else:
            # If no final message (e.g., initial URL error), try deleting the processing message
            try:
                await bot.delete_message(chat_id, processing_msg.message_id)
            except Exception:
                pass # Ignore deletion errors


        gc.collect() # Request garbage collection

    except Exception as e:
        logger.critical(f"Unhandled error in process_download for URL {url} (ChatID: {chat_id}): {e}", exc_info=True)
        error_report_msg = f"❌ **An unexpected critical error occurred processing your request.**\n`{e}`\nPlease try again later or report the issue if it persists."
        if processing_msg:
            try:
                await bot.edit_message_text(error_report_msg, chat_id, processing_msg.message_id, disable_web_page_preview=True)
            except Exception:
                await send_message(chat_id, error_report_msg)
        else:
             await send_message(chat_id, error_report_msg)
        # Also cleanup any potential leftover file if path is known (less likely here)
        # try: ... os.remove ... except: pass


async def worker():
    """Worker function for parallel processing of downloads from the queue."""
    worker_name = asyncio.current_task().get_name() # Get worker name if set
    logger.info(f"{worker_name} started.")

    # Ensure Mega is initialized within the worker's loop context if needed,
    # but the global initialization in main() should handle the first time.
    if not mega_logged_in:
        logger.info(f"{worker_name}: Ensuring Mega client is initialized...")
        await initialize_mega() # Ensure it's ready before processing tasks

    while True:
        task = await download_queue.get()
        message: Optional[Message] = None # Keep track of message for error reporting
        task_info_str = "Unknown task type"

        try:
            # Extract message object for logging/error reporting
            if isinstance(task, tuple) and len(task) > 0 and isinstance(task[0], Message):
                message = task[0]
                chat_id = message.chat.id
                user_id = message.from_user.id if message.from_user else "UnknownUser"
                task_info_str = f"ChatID: {chat_id}, User: {user_id}, "
                if len(task) == 2: task_info_str += f"Type: /image, URL: {task[1][:50]}..."
                elif len(task) == 7: task_info_str += f"Type: General/Audio/Trim, URL: {task[1][:50]}..."
                else: task_info_str += f"Type: Malformed Tuple len={len(task)}"
            else:
                 task_info_str = f"Task data: {str(task)[:100]}"


            logger.info(f"{worker_name} processing task: {task_info_str}")

            # --- Task Dispatch Logic ---
            if isinstance(task, tuple) and len(task) == 2 and isinstance(task[0], Message) and isinstance(task[1], str):
                 # Structure from /image command handler
                 msg_obj, url = task
                 logger.info(f"{worker_name} dispatching task (type /image) to process_download for URL: {url}")
                 await process_download(msg_obj, url) # Let process_download handle platform detection

            elif isinstance(task, tuple) and len(task) == 7 and isinstance(task[0], Message):
                 # Standard download/trim task
                 msg_obj, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time = task
                 logger.info(f"{worker_name} dispatching task (type general/audio/trim) to process_download for URL: {url}")
                 await process_download(msg_obj, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time)
            else:
                 logger.warning(f"{worker_name} received unknown or malformed task format: {task}")
                 if message: # Try to inform user if we have the message object
                      await send_message(message.chat.id, "❌ Internal error: Bot received a malformed task. Please try again.")


        except Exception as worker_error:
             logger.error(f"Error occurred processing task in {worker_name}: {worker_error}", exc_info=True)
             # Try to inform the user if possible
             if message:
                  await send_message(message.chat.id, f"❌ An internal error occurred in the worker processing your request. Please try again.")

        finally:
             download_queue.task_done()
             logger.debug(f"{worker_name} finished task, calling task_done()")
             gc.collect() # Run garbage collection after each task


# --- Telegram Bot Handlers ---

@bot.message_handler(commands=["start", "help"])
async def send_welcome(message: Message):
    """Sends welcome message with bot instructions."""
    # Updated welcome text for clarity
    welcome_text = (
        "🤖 **Media Download Bot** 🤖\n\n"
        "I can help you download media from various platforms. Just send me a link!\n\n"
        "➡️ **How to Use:**\n"
        "1. Send the URL of the video, image, post, or audio you want.\n"
        "2. I'll try to download it and send it back.\n"
        "3. For large files (> ~48MB), I'll upload to Mega.nz (requires setup) and give you the link.\n\n"
        "⚙️ **Specific Commands:**\n"
        "`/audio <URL>` - Extract only the audio from a video URL.\n"
        "`/image <URL>` - Download images/videos from an Instagram post/story URL (usually sending the URL directly works too).\n"
        "`/trim <URL> <Start> <End>` - Trim a video. Times like `HH:MM:SS` or `M:SS`.\n"
        "`/trimAudio <URL> <Start> <End>` - Trim audio. Times like `HH:MM:SS` or `M:SS`.\n\n"
        "✂️ **Trim Examples:**\n"
        "`/trim https://... 0:30 1:15` (Trim from 30s to 1m 15s)\n"
        "`/trimAudio https://... 00:10:05 00:12:00`\n\n"
        "**Supported Sites Include:**\n"
        "YouTube, Instagram, Facebook, Twitter/X, and potentially others.\n\n"
        "_Note: Success depends on the site structure and library compatibility._"
    )
    await send_message(message.chat.id, welcome_text, parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=["audio"])
async def handle_audio_request(message: Message):
    """Handles /audio command."""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await send_message(message.chat.id, "⚠️ Please provide a URL after `/audio`.\nExample: `/audio https://youtube.com/watch?v=...`", parse_mode="Markdown")
        return
    url = parts[1].strip()
    # Basic URL validation
    if not re.match(r"https?://\S+", url):
         await send_message(message.chat.id, "⚠️ Invalid URL provided. It should start with `http://` or `https://`.", parse_mode="Markdown")
         return

    # Use the 7-tuple format for the queue
    await download_queue.put((message, url, True, False, False, None, None))
    await send_message(message.chat.id, "✅ Added URL to the audio extraction queue!")

@bot.message_handler(commands=["image"])
async def handle_image_request(message: Message):
    """Handles /image command (now primarily for Instagram posts/stories)."""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await send_message(message.chat.id, "⚠️ Please provide an Instagram URL after `/image`.\nExample: `/image https://instagram.com/p/abc...`", parse_mode="Markdown")
        return
    url = parts[1].strip()

    # Check if URL is Instagram (basic check)
    if not PLATFORM_PATTERNS["Instagram"].search(url):
        await send_message(message.chat.id, "⚠️ This command is intended for Instagram post/story URLs (`/p/`, `/stories/`). For other media, just send the URL directly.", parse_mode="Markdown")
        return
    # Check if it's likely a post/story URL structure
    if "/p/" not in url and "/stories/" not in url:
        await send_message(message.chat.id, "ℹ️ For Instagram Reels or TV, just send the URL directly without the `/image` command.", parse_mode="Markdown")
        # Optionally still queue it, or return
        # return

    # Add to download queue using the simplified 2-tuple format, recognized by the worker
    await download_queue.put((message, url))
    await send_message(message.chat.id, "✅ Added Instagram URL to the download queue!")


@bot.message_handler(commands=["trim"])
async def handle_video_trim_request(message: Message):
    """Handles /trim command for video."""
    # Regex to capture URL and two timestamps (HH:MM:SS or M:SS or S)
    match = re.search(r"/trim\s+(https?://[^\s]+)\s+([\d:.]+)\s+([\d:.]+)", message.text, re.IGNORECASE)
    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format. Use:\n`/trim <URL> <StartTime> <EndTime>`\n"
            "Times like `HH:MM:SS`, `M:SS`, `SS` (e.g., `0:10`, `1:15:30`, `95`)\n"
            "Example: `/trim https://... 0:10.5 55`",
             parse_mode="Markdown"
        )
        return

    url, start_time, end_time = match.groups()
    # TODO: Add more robust validation for timestamp formats if needed using helper function
    # Use the 7-tuple format for the queue
    await download_queue.put((message, url, False, True, False, start_time, end_time))
    await send_message(message.chat.id, "✅ Added video trimming task to the queue!")

@bot.message_handler(commands=["trimAudio"])
async def handle_audio_trim_request(message: Message):
    """Handles /trimAudio command."""
    match = re.search(r"/trimAudio\s+(https?://[^\s]+)\s+([\d:.]+)\s+([\d:.]+)", message.text, re.IGNORECASE)
    if not match:
        await send_message(
            message.chat.id,
             "⚠️ Invalid format. Use:\n`/trimAudio <URL> <StartTime> <EndTime>`\n"
             "Times like `HH:MM:SS`, `M:SS`, `SS` (e.g., `0:10`, `1:15:30`, `95`)\n"
             "Example: `/trimAudio https://... 60 90.5`",
             parse_mode="Markdown"
        )
        return

    url, start_time, end_time = match.groups()
    # TODO: Add more robust validation for timestamp formats
    # Use the 7-tuple format for the queue
    await download_queue.put((message, url, False, False, True, start_time, end_time))
    await send_message(message.chat.id, "✅ Added audio trimming task to the queue!")

# General message handler for URLs (must be last text handler)
@bot.message_handler(func=lambda message: message.content_type == 'text' and not message.text.startswith('/'))
async def handle_message(message: Message):
    """Handles general text messages, assuming they are URLs for download."""
    url = message.text.strip()
    # Improved URL validation (basic check for scheme and some domain part)
    if not re.match(r"https?://\S+\.\S+", url): # Check for http(s):// followed by domain.something
         # Avoid sending error for casual chat messages
         # logger.info(f"Ignoring non-URL text message from {message.chat.id}: {message.text[:100]}")
         # Let user know if it looks like they *tried* to send a link?
         if "://" in url or "." in url.split("/")[-1]: # Heuristic: might be a malformed link
              await send_message(message.chat.id, "🤔 That doesn't look like a valid URL I can process. Please check the link format (should start with http:// or https://).")
         # else: just ignore casual chat
         return

    # Add general URLs to the download queue using the 7-tuple format
    await download_queue.put((message, url, False, False, False, None, None))
    logger.info(f"Added general URL from {message.chat.id} (User: {message.from_user.id if message.from_user else 'N/A'}) to queue: {url}")
    await send_message(message.chat.id, "✅ Added URL to the download queue!")


# --- Main Execution ---
async def main():
    """Initializes Mega, starts workers, and runs the bot polling."""
    logger.info("--- Bot Starting Up ---")
    # Initialize Mega.nz client first
    mega_ready = await initialize_mega()
    if not mega_ready:
        logger.critical("Failed to initialize Mega.nz client on startup.")
        logger.warning("Bot will continue running, but uploads to Mega.nz WILL FAIL.")
        # uncomment return to exit if Mega is essential
        # return

    # Start worker tasks
    # Consider making num_workers configurable (e.g., from environment variable or config.py)
    num_workers = min(4, (os.cpu_count() or 1) * 2) # Adjusted worker count slightly
    logger.info(f"Starting {num_workers} download worker tasks...")
    worker_tasks = []
    for i in range(num_workers):
        task = asyncio.create_task(worker(), name=f"Worker-{i+1}")
        worker_tasks.append(task)
        logger.info(f"Worker-{i+1} task created.")

    # Start polling
    logger.info("Starting Telegram bot polling...")
    stop_event = asyncio.Event() # For potential future graceful stop mechanisms

    try:
        # CHANGED: Corrected none_stop to non_stop
        await bot.polling(non_stop=True, timeout=30, request_timeout=30, logger_level=logging.INFO)
        # Keep main running until interrupted (non_stop=True handles this)
        await stop_event.wait()

    except asyncio.CancelledError:
        logger.info("Main polling task cancelled.")
    except Exception as e:
        logger.critical(f"Bot polling loop encountered a critical error: {e}", exc_info=True)
        # Potentially try to restart polling after a delay? Or just exit.
    finally:
        logger.info("--- Bot Shutting Down ---")

        # Gracefully cancel worker tasks
        logger.info("Cancelling worker tasks...")
        for i, task in enumerate(worker_tasks):
             if not task.done():
                 task.cancel()
                 logger.info(f"Cancel requested for {task.get_name()}")

        # Wait for workers to finish cancelling
        results = await asyncio.gather(*worker_tasks, return_exceptions=True)
        for i, res in enumerate(results):
             worker_name = f"Worker-{i+1}" # Assuming order matches creation
             if isinstance(res, asyncio.CancelledError):
                  logger.info(f"{worker_name} cancelled successfully.")
             elif isinstance(res, Exception):
                  # Try to get worker name from task if gather preserved it
                  # task_name = worker_tasks[i].get_name() if i < len(worker_tasks) else worker_name
                  logger.error(f"{worker_name} finished with error during shutdown: {res}", exc_info=res)
             else:
                  logger.info(f"{worker_name} finished normally during shutdown (unexpected if cancelled).")

        logger.info("Workers cancellation process complete.")

        # No explicit mega logout seems available or typically needed in mega.py
        # Session might timeout or be implicitly closed.

        logger.info("Bot shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually (KeyboardInterrupt).")
    except Exception as main_err:
         logger.critical(f"Critical error in main execution block: {main_err}", exc_info=True)

