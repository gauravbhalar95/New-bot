# bot_main.py
import os
import gc
import logging
import asyncio
import aiofiles
import re
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message # Import Message type hint

# Import configuration
from config import API_TOKEN, TELEGRAM_FILE_LIMIT

# Import processing functions and constants from the other file
from processing import (
    process_media_download,
    process_instagram_image_download,
    upload_to_dropbox,
    cleanup_file,
    PLATFORM_PATTERNS, # Import for URL validation in handlers
    detect_platform, # Import for deciding which process function to call initially
)
from utils.logger import setup_logging # Import the setup function

# Logging setup
logger = setup_logging(logging.DEBUG) # Initialize logger for this part

# Async Telegram bot setup
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML") # Use HTML or Markdown consistently

# Download queue
download_queue = asyncio.Queue()

async def send_message(chat_id, text, parse_mode="HTML"):
    """Sends a message asynchronously with error handling."""
    try:
        # Use the bot's default parse_mode if not specified
        await bot.send_message(chat_id, text, parse_mode=parse_mode)
    except Exception as e:
        logger.error(f"Error sending message to chat {chat_id}: {e}")
        # Optionally, try sending a plain text fallback
        try:
            await bot.send_message(chat_id, f"Error displaying formatted message. Original content attempt: {text}", parse_mode=None)
        except Exception as fallback_e:
            logger.error(f"Fallback plain text send message also failed for chat {chat_id}: {fallback_e}")


async def process_and_send(message: Message, file_paths: list, is_audio=False, is_image=False):
    """Processes a list of files: sends to Telegram or uploads to Dropbox."""
    if not file_paths:
        logger.warning(f"process_and_send called with empty file_paths for chat {message.chat.id}")
        # No need to send another failure message if the worker already did
        return

    for file_path in file_paths:
        if not file_path or not os.path.exists(file_path):
            logger.warning(f"File path invalid or does not exist in process_and_send: {file_path}")
            continue

        file_to_process = file_path # Keep track of the file to maybe cleanup

        try:
            file_size = os.path.getsize(file_path)
            logger.info(f"Processing file {os.path.basename(file_path)} ({file_size} bytes) for chat {message.chat.id}")

            # Check if file exceeds Telegram limit (use configured limit)
            if file_size > TELEGRAM_FILE_LIMIT:
                await send_message(message.chat.id, f"⏳ File is large ({file_size / (1024*1024):.2f} MB), attempting Dropbox upload...")
                filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                dropbox_link = await upload_to_dropbox(file_path, filename)

                if dropbox_link:
                    logger.info(f"Successfully uploaded large file to Dropbox: {dropbox_link}")
                    await send_message(
                        message.chat.id,
                        f"✅ File too large for Telegram.\n📥 <a href='{dropbox_link}'>Download from Dropbox</a>"
                    )
                else:
                    logger.error("Dropbox upload failed for large file.")
                    # We don't have the original direct download URL here usually
                    await send_message(message.chat.id, "❌ File is too large, and Dropbox upload failed.")

            else: # File size is within Telegram limits
                try:
                    async with aiofiles.open(file_path, "rb") as file:
                        # Send based on type
                        if is_image:
                            logger.info(f"Sending image {os.path.basename(file_path)} to {message.chat.id}")
                            await bot.send_photo(message.chat.id, file, timeout=120) # Increased timeout for photos
                        elif is_audio:
                            logger.info(f"Sending audio {os.path.basename(file_path)} to {message.chat.id}")
                            await bot.send_audio(message.chat.id, file, timeout=600)
                        else: # Assumed video
                            logger.info(f"Sending video {os.path.basename(file_path)} to {message.chat.id}")
                            await bot.send_video(message.chat.id, file, supports_streaming=True, timeout=600)
                        logger.info(f"Successfully sent file {os.path.basename(file_path)} to Telegram chat {message.chat.id}")

                except Exception as send_error:
                    logger.error(f"Error sending file {os.path.basename(file_path)} directly to Telegram: {send_error}", exc_info=True)
                    # Check for specific Telegram errors like 'Request Entity Too Large'
                    if "413" in str(send_error) or "too large" in str(send_error).lower():
                        await send_message(message.chat.id, f"⏳ Telegram rejected the file (likely size), attempting Dropbox upload...")
                        filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                        dropbox_link = await upload_to_dropbox(file_path, filename)
                        if dropbox_link:
                             await send_message(
                                message.chat.id,
                                f"✅ File was too large for Telegram.\n📥 <a href='{dropbox_link}'>Download from Dropbox</a>"
                             )
                        else:
                             await send_message(message.chat.id, "❌ File too large for Telegram, and Dropbox upload failed.")
                    else:
                        await send_message(message.chat.id, f"❌ Error sending file: {str(send_error)}")

        except Exception as outer_err:
             logger.error(f"Outer error processing file {file_path} for chat {message.chat.id}: {outer_err}", exc_info=True)
             await send_message(message.chat.id, f"❌ An unexpected error occurred while handling the file: {outer_err}")

        finally:
            # Cleanup the processed file regardless of success/failure
            cleanup_file(file_to_process)


# Worker for parallel download tasks
async def worker():
    """Worker function for parallel processing of downloads from the queue."""
    while True:
        task_info = None # Initialize to ensure it's defined in case of early continue/break
        try:
            task_info = await download_queue.get()
            message = task_info['message']
            task_type = task_info['type']

            logger.info(f"Worker received task: Type={task_type}, ChatID={message.chat.id}")

            if task_type == "image":
                url = task_info['url']
                await send_message(message.chat.id, "🖼️ Processing Instagram image...")
                file_paths = await process_instagram_image_download(url)
                if file_paths:
                     await process_and_send(message, file_paths, is_image=True)
                     await send_message(message.chat.id, "✅ Instagram image(s) processed!")
                else:
                     await send_message(message.chat.id, "❌ Image download failed or no images found.")

            elif task_type == "media":
                url = task_info['url']
                is_audio = task_info['is_audio']
                is_video_trim = task_info['is_video_trim']
                is_audio_trim = task_info['is_audio_trim']
                start_time = task_info['start_time']
                end_time = task_info['end_time']

                request_type = "Video Download"
                if is_audio: request_type = "Audio Download"
                elif is_video_trim: request_type = "Video Trimming"
                elif is_audio_trim: request_type = "Audio Trimming"

                await send_message(message.chat.id, f"⏳ Processing your {request_type.lower()}...")
                logger.info(f"Processing URL: {url}, Type: {request_type}")

                file_paths, _, _ = await process_media_download(
                    url, is_audio, is_video_trim, is_audio_trim, start_time, end_time
                ) # We mainly need the paths here, size/url handled by process_and_send

                if file_paths:
                     await process_and_send(message, file_paths, is_audio=(is_audio or is_audio_trim))
                     await send_message(message.chat.id, f"✅ {request_type} processed!")
                else:
                     await send_message(message.chat.id, f"❌ {request_type} failed. No media found or error occurred.")

        except ValueError as ve: # Catch specific errors from processing functions
            logger.warning(f"Value error during processing task for chat {message.chat.id}: {ve}")
            if task_info: # Ensure message is available
                await send_message(task_info['message'].chat.id, f"⚠️ Processing Error: {ve}")
            else:
                logger.error("Task info not available for value error message.")
        except Exception as e:
            logger.error(f"Critical error in worker processing task: {e}", exc_info=True)
            if task_info: # Ensure message is available
                 await send_message(task_info['message'].chat.id, f"❌ An unexpected error occurred during processing: {e}")
            else:
                logger.error("Task info not available for critical error message.")
        finally:
            if task_info: # Only call task_done if get() was successful
                download_queue.task_done()
            gc.collect() # Encourage garbage collection after each task


# === Telegram Command Handlers ===

@bot.message_handler(commands=["start", "help"])
async def send_welcome(message: Message):
    """Sends welcome message with bot instructions."""
    welcome_text = (
        "<b>🤖 Media Download Bot 🤖</b>\n\n"
        "I can help you download media from various platforms like YouTube, Instagram, Facebook, Twitter/X.\n\n"
        "<b>How to use:</b>\n"
        "➡️ Just send me the URL of the video/media you want to download.\n\n"
        "<b>Commands:</b>\n"
        "🎵 <code>/audio &lt;URL&gt;</code> - Extract and send the full audio.\n"
        "🖼️ <code>/image &lt;Instagram URL&gt;</code> - Download images from an Instagram post.\n"
        "✂️🎬 <code>/trim &lt;URL&gt; HH:MM:SS HH:MM:SS</code> - Trim a video segment.\n"
        "✂️🎵 <code>/trimAudio &lt;URL&gt; HH:MM:SS HH:MM:SS</code> - Extract an audio segment.\n\n"
        "<b>Examples:</b>\n"
        "<code>/image https://www.instagram.com/p/Cxyz.../</code>\n"
        "<code>/trim https://www.youtube.com/watch?v=abc... 00:01:00 00:02:30</code>\n"
        "<code>/trimAudio https://www.youtube.com/watch?v=abc... 00:00:15 00:00:45</code>\n\n"
        "<i>Note: Files larger than Telegram's limit (~50MB) will be uploaded to Dropbox.</i>"
    )
    await send_message(message.chat.id, welcome_text)

@bot.message_handler(commands=["audio"])
async def handle_audio_request(message: Message):
    """Handles audio extraction requests."""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await send_message(message.chat.id, "⚠️ Please provide a URL after the /audio command.\nExample: <code>/audio https://...</code>")
        return

    url = parts[1].strip()
    # Basic URL structure check (optional but good)
    if not re.match(r"^https?://", url):
         await send_message(message.chat.id, "⚠️ Invalid URL provided. Please make sure it starts with http:// or https://.")
         return

    task = {
        'type': 'media', 'message': message, 'url': url,
        'is_audio': True, 'is_video_trim': False, 'is_audio_trim': False,
        'start_time': None, 'end_time': None
    }
    await download_queue.put(task)
    await send_message(message.chat.id, "✅ Added to audio extraction queue!")

@bot.message_handler(commands=["image"])
async def handle_image_request(message: Message):
    """Handles Instagram image download requests."""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await send_message(message.chat.id, "⚠️ Please provide an Instagram URL after the /image command.\nExample: <code>/image https://www.instagram.com/p/...</code>")
        return

    url = parts[1].strip()
    # Check if URL is likely Instagram
    if not PLATFORM_PATTERNS["Instagram"].search(url):
        await send_message(message.chat.id, "⚠️ This command currently only supports <b>Instagram</b> URLs.")
        return

    task = {'type': 'image', 'message': message, 'url': url}
    await download_queue.put(task)
    await send_message(message.chat.id, "✅ Added to image download queue!")


# Regex for trim commands (captures URL and times)
TRIM_COMMAND_REGEX = re.compile(r"^\/(trim|trimAudio)\s+(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})$", re.IGNORECASE)

@bot.message_handler(commands=["trim", "trimAudio"])
async def handle_trim_request(message: Message):
    """Handles video and audio trimming requests."""
    match = TRIM_COMMAND_REGEX.match(message.text.strip())
    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format. Use:\n<code>/trim &lt;URL&gt; HH:MM:SS HH:MM:SS</code>\nor\n<code>/trimAudio &lt;URL&gt; HH:MM:SS HH:MM:SS</code>"
        )
        return

    command, url, start_time, end_time = match.groups()
    is_video_trim = command.lower() == "trim"
    is_audio_trim = command.lower() == "trimaudio"

    # Optional: Add time validation if needed (e.g., start < end)

    task = {
        'type': 'media', 'message': message, 'url': url,
        'is_audio': False, 'is_video_trim': is_video_trim, 'is_audio_trim': is_audio_trim,
        'start_time': start_time, 'end_time': end_time
    }
    await download_queue.put(task)
    queue_message = "video trimming" if is_video_trim else "audio segment extraction"
    await send_message(message.chat.id, f"✅ Added to {queue_message} queue!")

@bot.message_handler(func=lambda message: True, content_types=["text"])
async def handle_message(message: Message):
    """Handles general messages, attempting to treat them as URLs for video download."""
    url = message.text.strip()

    # Basic URL validation (check for http/https)
    if not re.match(r"^https?://[^\s]+", url):
        # Avoid responding to casual chat, only respond if it looks like a failed command or URL attempt
        if url.startswith('/'):
             await send_message(message.chat.id, "❓ Unknown command. Send /help to see available commands.")
        # else: Do nothing for random text
        return

    # Check if it's an adult site URL (optional, depending on desired behavior)
    platform = detect_platform(url)
    if platform == "Adult":
         await send_message(message.chat.id, "🔞 Downloading from this type of site is not supported directly via URL. Please use appropriate commands if available or contact the administrator.")
         return

    # Assume it's a video download request
    task = {
        'type': 'media', 'message': message, 'url': url,
        'is_audio': False, 'is_video_trim': False, 'is_audio_trim': False,
        'start_time': None, 'end_time': None
    }
    await download_queue.put(task)
    await send_message(message.chat.id, "✅ Added to download queue!")

# === Main Bot Runner ===
async def main():
    """Initializes workers and starts the bot polling."""
    # Determine number of workers (e.g., based on CPU or a fixed number)
    num_workers = min(4, (os.cpu_count() or 1) + 1) # Example: Use up to 4 workers
    logger.info(f"Starting {num_workers} worker tasks...")
    worker_tasks = []
    for i in range(num_workers):
        task = asyncio.create_task(worker())
        worker_tasks.append(task)
        logger.info(f"Worker {i+1} started.")

    logger.info("Starting bot polling...")
    try:
        await bot.infinity_polling(logger_level=logging.INFO, timeout=30) # Adjusted timeout
    except asyncio.CancelledError:
         logger.info("Bot polling cancelled.")
    except Exception as e:
        logger.error(f"Bot polling encountered an unrecoverable error: {e}", exc_info=True)
    finally:
        logger.info("Shutting down workers...")
        for task in worker_tasks:
            task.cancel()
        await asyncio.gather(*worker_tasks, return_exceptions=True) # Wait for workers to finish cancelling
        logger.info("Bot shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually (KeyboardInterrupt).")

