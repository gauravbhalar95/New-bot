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
from config import API_TOKEN, TELEGRAM_FILE_LIMIT, DROPBOX_ACCESS_TOKEN
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import process_video_trim, process_audio_trim
from utils.logger import setup_logging
from handlers.image_handlers import process_instagram_image # Ensure this is correctly imported

# Logging setup
logger = setup_logging(logging.DEBUG)

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")
download_queue = asyncio.Queue()

# Dropbox client setup
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

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
    "Instagram": process_instagram, # Default handler for videos/reels
    "Facebook": process_facebook,
    "Twitter/X": download_twitter_media,
    "Adult": process_adult,
    # Note: Instagram image handler is called conditionally within process_download
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
        str: Shareable link to the uploaded file or None on failure
    """
    try:
        # Validate access token
        try:
            dbx.users_get_current_account()
        except Exception as auth_error:
            logger.error(f"Dropbox authentication failed: {auth_error}")
            return None

        dropbox_path = f"/telegram_uploads/{filename}"

        # Use file upload with error handling
        with open(file_path, "rb") as f:
            file_size = os.path.getsize(file_path)

            # Check if file is too large for single upload (140MB threshold)
            if file_size > 140 * 1024 * 1024:
                logger.info("Large file detected, using upload session")
                upload_session_start_result = dbx.files_upload_session_start(f.read(4 * 1024 * 1024))
                cursor = dropbox.files.UploadSessionCursor(
                    session_id=upload_session_start_result.session_id,
                    offset=f.tell()
                )
                commit = dropbox.files.CommitInfo(path=dropbox_path, mode=dropbox.files.WriteMode.overwrite)

                while f.tell() < file_size:
                    chunk_size = 4 * 1024 * 1024
                    if (file_size - f.tell()) <= chunk_size:
                        logger.info(f"Finishing upload session for {filename}")
                        dbx.files_upload_session_finish(f.read(chunk_size), cursor, commit)
                        break
                    else:
                        dbx.files_upload_session_append_v2(f.read(chunk_size), cursor)
                        cursor.offset = f.tell()
            else:
                # Regular upload for smaller files
                logger.info(f"Uploading smaller file {filename} directly.")
                dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)

        # Create shared link with public visibility
        shared_link_settings = dropbox.sharing.SharedLinkSettings(
            requested_visibility=dropbox.sharing.RequestedVisibility.public
        )
        shared_link_metadata = dbx.sharing_create_shared_link_with_settings(
            dropbox_path, settings=shared_link_settings
        )
        # Return direct download link
        return shared_link_metadata.url.replace('?dl=0', '?dl=1').replace('&dl=0','&dl=1')

    except dropbox.exceptions.AuthError as auth_error:
        logger.error(f"Dropbox authentication error: {auth_error}")
        return None
    except dropbox.exceptions.ApiError as api_error:
        logger.error(f"Dropbox API error during upload for {filename}: {api_error}")
        return None
    except Exception as e:
        logger.error(f"Unexpected Dropbox upload error for {filename}: {e}", exc_info=True)
        return None


async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    """Handles media download and sends it to Telegram or Dropbox."""
    try:
        request_type = "Media Download" # Default type
        if is_audio:
            request_type = "Audio Download"
        elif is_video_trim:
            request_type = "Video Trimming"
        elif is_audio_trim:
            request_type = "Audio Trimming"
        # We don't need a specific type for Image, as the handler logic decides

        # Use a placeholder message initially
        processing_message = await bot.send_message(message.chat.id, f"⏳ **Processing your request...**")

        logger.info(f"Processing URL: {url}, Type Hint: {request_type}")

        # Detect platform
        platform = detect_platform(url)
        if not platform:
            await bot.edit_message_text("⚠️ **Unsupported URL.**", chat_id=message.chat.id, message_id=processing_message.message_id)
            return

        # Update status message
        await bot.edit_message_text(f"📥 **Processing {platform} URL for {request_type.lower()}...**", chat_id=message.chat.id, message_id=processing_message.message_id)


        # Handle request based on type
        file_paths = []
        file_size = None
        download_url = None # Primarily for fallback if needed

        if is_video_trim:
            logger.info(f"Processing video trim request: Start={start_time}, End={end_time}")
            result = await process_video_trim(url, start_time, end_time)
            if isinstance(result, tuple) and len(result) == 2:
                file_path, file_size = result
                file_paths = [file_path] if file_path else []
            else: # Handle potential errors from trim function
                 logger.error(f"Video trim failed or returned unexpected result: {result}")
                 file_paths = []

        elif is_audio_trim:
            logger.info(f"Processing audio trim request: Start={start_time}, End={end_time}")
            result = await process_audio_trim(url, start_time, end_time)
            if isinstance(result, tuple) and len(result) == 2:
                file_path, file_size = result
                file_paths = [file_path] if file_path else []
            else: # Handle potential errors from trim function
                 logger.error(f"Audio trim failed or returned unexpected result: {result}")
                 file_paths = []

        elif is_audio:
            result = await extract_audio_ffmpeg(url)
            if isinstance(result, tuple) and len(result) == 2:
                file_path, file_size = result
                file_paths = [file_path] if file_path else []
            elif isinstance(result, str) and os.path.exists(result): # Handle case where only path is returned
                file_path = result
                file_size = os.path.getsize(file_path) # Calculate size
                file_paths = [file_path]
            else:
                logger.error(f"Audio extraction failed or returned unexpected result: {result}")
                file_paths = []


        else: # General video/image download
            handler = PLATFORM_HANDLERS.get(platform)
            if not handler:
                 # This case should technically be caught by platform detection earlier
                 await bot.edit_message_text("⚠️ **Unsupported platform handler.**", chat_id=message.chat.id, message_id=processing_message.message_id)
                 return

            # --- Specific Instagram Logic ---
            if platform == "Instagram":
                # Determine if it's likely an image post (photo/carousel) or video/reel based on URL
                # This logic handles both direct URLs and `/image` command URLs
                if "/p/" in url or "/reel/" not in url:
                    logger.info(f"Detected Instagram image/carousel URL: {url}")
                    await bot.edit_message_text("🖼️ **Processing Instagram image/carousel...**", chat_id=message.chat.id, message_id=processing_message.message_id)
                    result = await process_instagram_image(url)
                    request_type = "Image Download" # Update request type display name
                else:
                    logger.info(f"Detected Instagram video/reel URL: {url}")
                    await bot.edit_message_text("🎬 **Processing Instagram video/reel...**", chat_id=message.chat.id, message_id=processing_message.message_id)
                    result = await process_instagram(url) # Use the standard video/reel handler
                    request_type = "Video Download"
            # --- End Specific Instagram Logic ---
            else:
                 # For other platforms, call the assigned handler directly
                 await bot.edit_message_text(f"⚙️ **Processing {platform} media...**", chat_id=message.chat.id, message_id=processing_message.message_id)
                 result = await handler(url)
                 # Assuming video unless explicitly audio/trim
                 if not is_audio and not is_video_trim and not is_audio_trim:
                     request_type = "Video Download"


            # Standardize result processing (assuming handlers return paths, size, url)
            if isinstance(result, tuple):
                 if len(result) >= 3:
                     raw_paths, file_size, download_url = result
                 elif len(result) == 2:
                     raw_paths, file_size = result
                     download_url = None
                 else: # Unexpected tuple format
                     logger.warning(f"Handler for {platform} returned unexpected tuple format: {result}")
                     raw_paths = None
            elif isinstance(result, list): # Handler returned a list of paths
                 raw_paths = result
                 file_size = None # Will recalculate later if needed
                 download_url = None
            elif isinstance(result, str) and os.path.exists(result): # Handler returned a single path
                 raw_paths = [result]
                 file_size = None # Will recalculate later if needed
                 download_url = None
            else: # Handler failed or returned None/empty
                 logger.warning(f"Handler for {platform} did not return valid file paths. Result: {result}")
                 raw_paths = None

            # Ensure file_paths is always a list, even if empty or None
            file_paths = raw_paths if isinstance(raw_paths, list) else [raw_paths] if raw_paths else []


        # Log what we received before processing files
        logger.info(f"Handler returned: file_paths={file_paths}, initial_file_size={file_size}, download_url={download_url}")

        # Cleanup processing message if files were found (or about to fail)
        # We'll send new messages for success/failure/upload links
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=processing_message.message_id)
        except Exception as del_err:
            logger.warning(f"Could not delete processing message: {del_err}")


        # Skip further processing if no valid file paths were returned
        if not file_paths or all(path is None or not os.path.exists(path) for path in file_paths):
            logger.warning("No valid file paths found after processing.")
            await send_message(message.chat.id, f"❌ **{request_type} failed. No media could be retrieved.**")
            return

        # Process each file (e.g., for Instagram carousels)
        sent_media_count = 0
        for file_path in file_paths:
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"Skipping non-existent file path: {file_path}")
                continue

            # Get current file size accurately
            current_file_size = os.path.getsize(file_path)
            filename = os.path.basename(file_path) # Get filename for Dropbox/logging

            # Determine media type for sending
            is_current_file_audio = is_audio or is_audio_trim or filename.lower().endswith(('.mp3', '.m4a', '.ogg', '.wav', '.flac'))
            # Add more image extensions if needed
            is_current_file_image = not is_current_file_audio and filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif'))


            # Check against Telegram limit (use a slightly safer margin, e.g., 49MB)
            safe_telegram_limit = 49 * 1024 * 1024
            if current_file_size > TELEGRAM_FILE_LIMIT or current_file_size > safe_telegram_limit:
                logger.info(f"File '{filename}' too large for Telegram: {current_file_size} bytes. Uploading to Dropbox.")
                await send_message(message.chat.id, f"⏳ Uploading large file '{filename}' to Dropbox...")

                # Generate a unique Dropbox filename to avoid collisions
                unique_filename = f"{message.chat.id}_{message.message_id}_{filename}"
                dropbox_link = await upload_to_dropbox(file_path, unique_filename)

                if dropbox_link:
                    logger.info(f"Successfully uploaded '{filename}' to Dropbox: {dropbox_link}")
                    await send_message(
                        message.chat.id,
                        f"⚠️ **File '{filename}' is too large for Telegram.**\n📥 [Download from Dropbox]({dropbox_link})"
                    )
                    sent_media_count += 1
                else:
                    logger.warning(f"Dropbox upload failed for '{filename}'")
                    # Fallback to original download URL if available and useful
                    if download_url:
                         await send_message(
                             message.chat.id,
                             f"⚠️ **File '{filename}' too large, Dropbox upload failed.**\n GDrive URL [Download original]({download_url})"
                         )
                    else:
                         await send_message(message.chat.id, f"❌ **Upload failed for '{filename}'.**")
            else:
                # Send file via Telegram
                logger.info(f"Sending file '{filename}' via Telegram ({current_file_size} bytes). Audio: {is_current_file_audio}, Image: {is_current_file_image}")
                try:
                    # Use aiofiles for async file reading
                    async with aiofiles.open(file_path, "rb") as file:
                        # Send based on determined type
                        if is_current_file_audio:
                             await bot.send_audio(message.chat.id, file, caption=filename, timeout=600)
                        elif is_current_file_image:
                             await bot.send_photo(message.chat.id, file, caption=filename, timeout=600)
                        else: # Assume video
                             await bot.send_video(message.chat.id, file, caption=filename, supports_streaming=True, timeout=600)
                        sent_media_count += 1

                except Exception as send_error:
                    logger.error(f"Error sending file '{filename}' to Telegram: {send_error}", exc_info=True)

                    # Check for specific errors like 413 Payload Too Large
                    if "413" in str(send_error) or "too large" in str(send_error).lower():
                        logger.info(f"Got size-related error sending '{filename}' via Telegram, attempting Dropbox upload as fallback.")
                        await send_message(message.chat.id, f"⏳ Telegram rejected '{filename}' due to size. Trying Dropbox...")
                        unique_filename = f"{message.chat.id}_{message.message_id}_{filename}"
                        dropbox_link = await upload_to_dropbox(file_path, unique_filename)

                        if dropbox_link:
                            await send_message(
                                message.chat.id,
                                f"⚠️ **File '{filename}' too large for Telegram.**\n📥 [Download from Dropbox]({dropbox_link})"
                            )
                            sent_media_count += 1
                        else:
                            await send_message(message.chat.id, f"❌ **Upload failed for '{filename}' (Telegram rejected & Dropbox failed).**")
                    else:
                        # General send error
                        await send_message(message.chat.id, f"❌ **Error sending file '{filename}':** `{str(send_error)}`")

            # Cleanup the processed file immediately
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Cleaned up file: {file_path}")
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up file {file_path}: {cleanup_error}")

        # Final status message if no media was successfully sent/uploaded
        if sent_media_count == 0:
             logger.warning(f"Processed {len(file_paths)} files but failed to send/upload any.")
             # Check if initial processing message was deleted, if not, edit it
             try:
                 await bot.edit_message_text(f"❌ **{request_type} failed. Could not send or upload media.**", chat_id=message.chat.id, message_id=processing_message.message_id)
             except Exception: # Message likely deleted or already edited
                 await send_message(message.chat.id, f"❌ **{request_type} failed. Could not send or upload media.**")


    except Exception as e:
        logger.error(f"Comprehensive error in process_download for URL {url}: {e}", exc_info=True)
        # Try to edit the status message if it exists, otherwise send a new one
        try:
             await bot.edit_message_text(f"❌ **An unexpected error occurred:** `{e}`", chat_id=message.chat.id, message_id=processing_message.message_id)
        except Exception:
             await send_message(message.chat.id, f"❌ **An unexpected error occurred:** `{e}`")

    finally:
         # Force garbage collection after processing potentially large files
         gc.collect()


async def worker():
    """Worker function for parallel processing of downloads."""
    while True:
        try:
            task = await download_queue.get()
            # Unpack task based on expected number of items (now 7)
            if len(task) == 7:
                 message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time = task
                 await process_download(message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time)
            else:
                 logger.error(f"Worker received task with unexpected number of items: {len(task)}")
                 # Handle error appropriately, maybe notify user associated with the message if possible
                 if task and hasattr(task[0], 'chat'):
                     await send_message(task[0].chat.id, "❌ Internal error processing your request (invalid task format).")

        except Exception as worker_err:
             logger.error(f"Error in worker loop: {worker_err}", exc_info=True)
             # Avoid crashing the worker, wait a bit before retrying
             await asyncio.sleep(5)
        finally:
             # Ensure task_done is called even if errors occur within processing
             download_queue.task_done()


@bot.message_handler(commands=["start", "help"])
async def send_welcome(message):
    """Sends welcome message with bot instructions."""
    welcome_text = (
        "🤖 *Media Download Bot* 🤖\n\n"
        "I can help you download media from various platforms:\n"
        "• YouTube (Video & Audio)\n"
        "• Instagram (Video, Reels, Images, Carousels)\n"
        "• Facebook (Video)\n"
        "• Twitter/X (Video & Images)\n\n"
        "**How to use:**\n"
        "1️⃣ Send a direct URL for video/reel/photo download.\n"
        "2️⃣ Use commands for specific actions:\n\n"
        "• `/image <Instagram URL>`\n   ↳ Download static image(s) from an Instagram post.\n\n"
        "• `/audio <URL>`\n   ↳ Extract full audio from a video (YouTube, etc.).\n\n"
        "• `/trim <URL> <Start> <End>`\n   ↳ Trim a video segment. Times in HH:MM:SS.\n   *Example:* `/trim <URL> 00:01:00 00:02:30`\n\n"
        "• `/trimAudio <URL> <Start> <End>`\n   ↳ Extract an audio segment. Times in HH:MM:SS.\n   *Example:* `/trimAudio <URL> 00:00:10 00:00:45`\n\n"
        "⚠️ *Large files (>50MB) will be uploaded to Dropbox.*\n"
        "ℹ️ Send `/help` to see this message again."
    )
    await send_message(message.chat.id, welcome_text)


@bot.message_handler(commands=["audio"])
async def handle_audio_request(message):
    """Handles audio extraction requests."""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await send_message(message.chat.id, "⚠️ **Please provide a URL after the command.**\nExample: `/audio <URL>`")
        return
    url = parts[1].strip()
    # Add task to queue: (message, url, is_audio, is_video_trim, is_audio_trim, start, end)
    await download_queue.put((message, url, True, False, False, None, None))
    await send_message(message.chat.id, "✅ **Added to audio extraction queue!**")

# --- NEW Image Handler ---
@bot.message_handler(commands=["image"])
async def handle_image_request(message):
    """Handles Instagram image download requests."""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await send_message(message.chat.id, "⚠️ **Please provide an Instagram URL after the command.**\nExample: `/image <Instagram Post URL>`")
        return
    url = parts[1].strip()
    if not PLATFORM_PATTERNS["Instagram"].search(url):
         await send_message(message.chat.id, "⚠️ **This command only works with Instagram URLs.**")
         return

    # Add task to queue: (message, url, is_audio, is_video_trim, is_audio_trim, start, end)
    # Note: We treat it as a standard download request; process_download handles the logic.
    await download_queue.put((message, url, False, False, False, None, None))
    await send_message(message.chat.id, "✅ **Added to Instagram image download queue!**")
# --- End NEW Image Handler ---

@bot.message_handler(commands=["trim"])
async def handle_video_trim_request(message):
    """Handles video trimming requests."""
    match = re.search(r"^\/trim\s+(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", message.text, re.IGNORECASE)
    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format. Use: `/trim <URL> <Start HH:MM:SS> <End HH:MM:SS>`"
        )
        return

    url, start_time, end_time = match.groups()
    # Add task to queue: (message, url, is_audio, is_video_trim, is_audio_trim, start, end)
    await download_queue.put((message, url, False, True, False, start_time, end_time))
    await send_message(message.chat.id, "✅ **Added to video trimming queue!**")

@bot.message_handler(commands=["trimAudio"])
async def handle_audio_trim_request(message):
    """Handles audio segment extraction requests."""
    match = re.search(r"^\/trimAudio\s+(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})", message.text, re.IGNORECASE)
    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format. Use: `/trimAudio <URL> <Start HH:MM:SS> <End HH:MM:SS>`"
        )
        return

    url, start_time, end_time = match.groups()
     # Add task to queue: (message, url, is_audio, is_video_trim, is_audio_trim, start, end)
    await download_queue.put((message, url, False, False, True, start_time, end_time))
    await send_message(message.chat.id, "✅ **Added to audio segment extraction queue!**")

@bot.message_handler(func=lambda message: detect_platform(message.text.strip()) is not None, content_types=["text"])
async def handle_url_message(message):
    """Handles general media download requests from supported URLs."""
    url = message.text.strip()
    platform = detect_platform(url) # Already checked by func, but good practice

    # Add task to queue: (message, url, is_audio, is_video_trim, is_audio_trim, start, end)
    # This handles standard video/image downloads based on URL detection
    await download_queue.put((message, url, False, False, False, None, None))
    await send_message(message.chat.id, f"✅ **Added {platform} URL to download queue!**")


@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_unknown_message(message):
    """Handles messages that are not commands or recognized URLs."""
    logger.info(f"Received unknown text message from {message.chat.id}: {message.text[:50]}")
    # Optionally, provide guidance or ignore silently
    # Example: Send help message if it doesn't look like a URL attempt
    if not re.search(r"https?://", message.text):
        await send_message(message.chat.id, "❓ Unrecognized command or URL. Send `/help` for instructions.")
    else: # It looked like a URL but wasn't detected by `detect_platform`
         await send_message(message.chat.id, "⚠️ Unsupported URL or platform. Send `/help` to see supported sites.")


async def main():
    """Runs the bot and initializes worker processes."""
    # Adjust worker count based on needs and resources
    num_workers = min(4, (os.cpu_count() or 1) + 1) # Example: Use CPU count + 1, capped at 4
    logger.info(f"Starting {num_workers} download workers...")
    workers = [asyncio.create_task(worker()) for _ in range(num_workers)]

    logger.info("Bot starting polling...")
    try:
        # Use longer timeout and skip pending updates on startup
        await bot.polling(non_stop=True, skip_pending=True, timeout=45)
    except Exception as e:
        logger.critical(f"Bot polling failed critically: {e}", exc_info=True)
    finally:
        logger.info("Bot polling stopped. Cancelling workers.")
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True) # Wait for workers to finish cancelling
        logger.info("Workers cancelled.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")
