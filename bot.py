import os
import gc
import logging
import asyncio
import aiofiles
import re
from mega import Mega
from telebot.async_telebot import AsyncTeleBot

# Import local modules
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

# MEGA client setup
mega = Mega()

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


async def upload_to_mega(file_path, filename, max_retries=3):
    """
    Uploads a file to MEGA.nz with retry logic and returns a shareable link.
    
    Args:
        file_path (str): Path to the file to upload
        filename (str): Name to use for the file in MEGA
        max_retries (int): Maximum number of retry attempts
        
    Returns:
        str: Shareable link to the uploaded file or None if upload fails
    """
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Use run_in_executor to run the blocking MEGA operations in a thread pool
            loop = asyncio.get_event_loop()
            
            # Login to MEGA with improved error handling
            try:
                # Create a fresh mega instance each attempt to avoid stale sessions
                mega_instance = Mega()
                
                # Log with credentials masked for security in logs
                masked_email = MEGA_EMAIL[0:3] + "***" + MEGA_EMAIL[-3:] if len(MEGA_EMAIL) > 6 else "***@***"
                logger.info(f"Attempting MEGA login with {masked_email} (attempt {retry_count+1}/{max_retries})")
                
                # Actual login
                mega_instance = await loop.run_in_executor(
                    None, 
                    lambda: mega_instance.login(MEGA_EMAIL, MEGA_PASSWORD)
                )
                logger.info("Successfully logged into MEGA")
                
            except Exception as auth_error:
                error_details = str(auth_error)
                logger.error(f"MEGA authentication failed: {error_details}")
                
                # Check for specific error conditions
                if "Invalid email" in error_details:
                    logger.error("Email appears to be invalid. Check your MEGA_EMAIL in config.")
                    return None  # No point retrying with invalid email
                    
                elif "Invalid password" in error_details:
                    logger.error("Password appears to be invalid. Check your MEGA_PASSWORD in config.")
                    return None  # No point retrying with invalid password
                    
                elif any(term in error_details.lower() for term in ["blocked", "rate", "limit", "too many"]):
                    wait_time = 60 * (retry_count + 1)  # Exponential backoff
                    logger.warning(f"Possible rate limiting detected, waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                else:
                    # Generic backoff for other errors
                    await asyncio.sleep(5 * (retry_count + 1))
                
                retry_count += 1
                if retry_count < max_retries:
                    logger.info(f"Retrying MEGA authentication (attempt {retry_count+1}/{max_retries})")
                    continue
                else:
                    logger.error("Maximum retry attempts reached for MEGA authentication")
                    return None
            
            # Upload the file
            try:
                logger.info(f"Uploading file to MEGA: {os.path.basename(file_path)}")
                upload_response = await loop.run_in_executor(
                    None,
                    lambda: mega_instance.upload(file_path, dest_filename=filename)
                )
                logger.info(f"File uploaded to MEGA successfully")
            except Exception as upload_error:
                error_details = str(upload_error)
                logger.error(f"MEGA upload error: {error_details}")
                
                if any(term in error_details.lower() for term in ["quota", "storage", "space"]):
                    logger.error("MEGA storage quota may be exceeded")
                    return None  # No point retrying if quota exceeded
                    
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 10 * (retry_count + 1)
                    logger.info(f"Retrying upload in {wait_time}s (attempt {retry_count+1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error("Maximum retry attempts reached for MEGA upload")
                    return None
            
            # Get the public link
            try:
                logger.info("Generating MEGA public link")
                file_link = await loop.run_in_executor(
                    None,
                    lambda: mega_instance.get_upload_link(upload_response)
                )
                logger.info(f"MEGA link generated successfully")
                return file_link
            except Exception as link_error:
                error_details = str(link_error)
                logger.error(f"Error generating MEGA link: {error_details}")
                
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 5 * (retry_count + 1)
                    logger.info(f"Retrying link generation in {wait_time}s (attempt {retry_count+1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error("Maximum retry attempts reached for MEGA link generation")
                    return None
        
        except Exception as e:
            logger.error(f"Unexpected MEGA upload error: {e}", exc_info=True)
            retry_count += 1
            if retry_count < max_retries:
                wait_time = 15 * retry_count
                logger.info(f"Retrying entire MEGA process in {wait_time}s (attempt {retry_count+1}/{max_retries})")
                await asyncio.sleep(wait_time)
            else:
                logger.error("Maximum retry attempts reached for MEGA process")
                return None
    
    return None  # If we've exhausted all retries


async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    """Handles video/audio download and sends it to Telegram or MEGA."""
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
                logger.info(f"File too large for Telegram: {file_size} bytes. Using MEGA.")
                mega_link = await upload_to_mega(file_path, filename)

                if mega_link:
                    logger.info(f"Successfully uploaded to MEGA: {mega_link}")
                    await send_message(
                        message.chat.id,
                        f"⚠️ **File too large for Telegram.**\n📥 [Download from MEGA]({mega_link})"
                    )
                else:
                    logger.warning("MEGA upload failed")
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
                            mega_link = await upload_to_mega(file_path, filename)

                            if mega_link:
                                await send_message(
                                    message.chat.id,
                                    f"⚠️ **File too large for Telegram.**\n📥 [Download from MEGA]({mega_link})"
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
                        logger.info("Got 413 error, attempting MEGA upload as fallback")
                        filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                        mega_link = await upload_to_mega(file_path, filename)

                        if mega_link:
                            await send_message(
                                message.chat.id,
                                f"⚠️ **File too large for Telegram.**\n📥 [Download from MEGA]({mega_link})"
                            )
                        else:
                            await send_message(message.chat.id, "❌ **File too large and MEGA upload failed.**")
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
    """Handles image download and sends it to Telegram or MEGA."""
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
                    logger.info(f"Image too large for Telegram: {file_size} bytes. Using MEGA.")

                    # Upload to MEGA
                    mega_link = await upload_to_mega(file_path, filename)

                    if mega_link:
                        logger.info(f"Successfully uploaded image to MEGA: {mega_link}")
                        await send_message(
                            message.chat.id,
                            f"⚠️ **Image too large for Telegram.**\n📥 [Download from MEGA]({mega_link})",
                            parse_mode="Markdown"
                        )
                    else:
                        logger.warning("MEGA upload failed")
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
        task = await download_queue.get()

        if len(task) == 2:
            # Image processing task
            message, url = task
            await process_image_download(message, url)
        else:
            # Regular download task
            message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time = task
            await process_download(message, url, is_audio, is_video_trim, is_audio_trim, start_time, end_time)

        download_queue.task_done()

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

# Main bot runner
async def main():
    """Runs the bot and initializes worker processes."""
    num_workers = min(3, os.cpu_count() or 1)
    for _ in range(num_workers):
        asyncio.create_task(worker())

    try:
        await bot.infinity_polling(timeout=30)
    except Exception as e:
        logger.error(f"Bot polling error: {e}")

if __name__ == "__main__":
    asyncio.run(main())