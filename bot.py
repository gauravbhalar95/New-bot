import os
import gc
import logging
import asyncio
import aiofiles
import re
import sys
import time
import psutil
from datetime import datetime, timezone
from mega import Mega
from telebot.async_telebot import AsyncTeleBot

# Import local modules
from config import (
    API_TOKEN, 
    TELEGRAM_FILE_LIMIT, 
    MEGA_EMAIL, 
    MEGA_PASSWORD,
    DEFAULT_ADMIN,
    ADMIN_IDS
)
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
mega = None

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

def get_current_utc():
    """Returns current UTC time in YYYY-MM-DD HH:MM:SS format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

async def send_message(chat_id, text):
    """Sends a message asynchronously."""
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"[{get_current_utc()}] Error sending message: {e}")

def detect_platform(url):
    """Detects the platform based on URL patterns."""
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None

async def get_mega_client():
    """Initializes or returns the MEGA client."""
    global mega
    if mega is None:
        try:
            m = Mega()
            mega = await asyncio.to_thread(m.login, MEGA_EMAIL, MEGA_PASSWORD)
            logger.info(f"[{get_current_utc()}] MEGA client initialized successfully")
        except Exception as e:
            logger.error(f"[{get_current_utc()}] Failed to initialize MEGA client: {e}")
            return None
    return mega

async def upload_to_mega(file_path, filename):
    """
    Uploads a file to MEGA and returns a shareable link using upload() and get_upload_link().
    """
    try:
        mega = await get_mega_client()
        if not mega:
            logger.error(f"[{get_current_utc()}] Failed to initialize MEGA client")
            return None

        logger.info(f"[{get_current_utc()}] Uploading file to MEGA: {filename}")
        
        # Use the exact method as provided: m.upload('myfile.doc')
        try:
            file = await asyncio.to_thread(mega.upload, file_path)
            logger.info(f"[{get_current_utc()}] Upload successful, file object: {file}")
            
            if not file:
                logger.error(f"[{get_current_utc()}] File upload failed - no file object returned")
                return None
                
            # Use the exact method as provided: m.get_upload_link(file)
            share_link = await asyncio.to_thread(mega.get_upload_link, file)
            
            if share_link and isinstance(share_link, str):
                logger.info(f"[{get_current_utc()}] Successfully generated MEGA link: {share_link}")
                return share_link
            else:
                logger.error(f"[{get_current_utc()}] Invalid share link generated")
                return None
                
        except Exception as upload_error:
            logger.error(f"[{get_current_utc()}] Error during upload or link generation: {upload_error}")
            return None

    except Exception as e:
        logger.error(f"[{get_current_utc()}] Unexpected error in upload_to_mega: {e}")
        return None

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
        logger.info(f"[{get_current_utc()}] Processing URL: {url}, Type: {request_type}")

        # Detect platform
        platform = detect_platform(url)
        if not platform:
            await send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        # Handle request based on type
        if is_video_trim:
            logger.info(f"[{get_current_utc()}] Processing video trim request: Start={start_time}, End={end_time}")
            file_path, file_size = await process_video_trim(url, start_time, end_time)
            download_url = None
            file_paths = [file_path] if file_path else []
        elif is_audio_trim:
            logger.info(f"[{get_current_utc()}] Processing audio trim request: Start={start_time}, End={end_time}")
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
                    result = await process_instagram(url)
                else:
                    result = await process_instagram_image(url)
            else:
                result = await PLATFORM_HANDLERS[platform](url)

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

        if not file_paths or all(not path for path in file_paths):
            logger.warning(f"[{get_current_utc()}] No valid file paths returned from platform handler")
            await send_message(message.chat.id, "❌ **Download failed. No media found.**")
            return

        for file_path in file_paths:
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"[{get_current_utc()}] File path does not exist: {file_path}")
                continue

            if file_size is None:
                file_size = os.path.getsize(file_path)

            if file_size > TELEGRAM_FILE_LIMIT or file_size > 49 * 1024 * 1024:
                filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                logger.info(f"[{get_current_utc()}] File too large for Telegram: {file_size} bytes. Using MEGA.")
                
                # Send upload status message
                status_msg = await bot.send_message(
                    message.chat.id,
                    "📤 Uploading file to MEGA... Please wait..."
                )
                
                mega_link = await upload_to_mega(file_path, filename)

                if mega_link:
                    logger.info(f"[{get_current_utc()}] Successfully uploaded to MEGA: {mega_link}")
                    try:
                        # Delete the status message
                        await bot.delete_message(message.chat.id, status_msg.message_id)
                        
                        # Send the download link
                        await bot.send_message(
                            message.chat.id,
                            f"✅ File uploaded successfully!\n\n"
                            f"📥 *Download from MEGA:*\n{mega_link}",
                            parse_mode="Markdown",
                            disable_web_page_preview=True
                        )
                        
                    except Exception as msg_error:
                        logger.error(f"[{get_current_utc()}] Error sending MEGA link message: {msg_error}")
                        # Fallback message in case of formatting issues
                        await send_message(
                            message.chat.id,
                            f"✅ File uploaded! Download link: {mega_link}"
                        )
                else:
                    logger.warning(f"[{get_current_utc()}] MEGA upload failed")
                    await bot.edit_message_text(
                        "❌ Upload to MEGA failed. Please try again.",
                        message.chat.id,
                        status_msg.message_id
                    )
                    if download_url:
                        await send_message(
                            message.chat.id,
                            f"⚠️ Alternative download link:\n{download_url}"
                        )
            else:
                try:
                    async with aiofiles.open(file_path, "rb") as file:
                        file_content = await file.read()
                        if is_audio or is_audio_trim:
                            await bot.send_audio(message.chat.id, file_content, timeout=600)
                        else:
                            await bot.send_video(message.chat.id, file_content, supports_streaming=True, timeout=600)

                except Exception as send_error:
                    logger.error(f"[{get_current_utc()}] Error sending file to Telegram: {send_error}")
                    if "413" in str(send_error):
                        logger.info(f"[{get_current_utc()}] Got 413 error, attempting MEGA upload as fallback")
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
                    logger.info(f"[{get_current_utc()}] Cleaned up file: {file_path}")
            except Exception as cleanup_error:
                logger.error(f"[{get_current_utc()}] Failed to clean up file {file_path}: {cleanup_error}")

        gc.collect()

    except Exception as e:
        logger.error(f"[{get_current_utc()}] Comprehensive error in process_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")

# Command handlers and main function will follow in the next part...


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

# Status command handler
@bot.message_handler(commands=["status"])
async def handle_status(message):
    """Shows the current status of the bot and download queue."""
    try:
        queue_size = download_queue.qsize()
        memory_usage = psutil.Process().memory_info().rss / 1024 / 1024  # in MB
        cpu_percent = psutil.Process().cpu_percent()
        uptime = time.time() - psutil.Process().create_time()
        
        status_text = (
            "🤖 **Bot Status**\n\n"
            f"📊 Queue Size: {queue_size} tasks\n"
            f"💾 Memory Usage: {memory_usage:.1f} MB\n"
            f"⚡ CPU Usage: {cpu_percent:.1f}%\n"
            f"⏱️ Uptime: {int(uptime/3600)}h {int((uptime%3600)/60)}m\n"
            f"👥 Active Workers: {min(3, os.cpu_count() or 1)}\n"
        )
        await bot.send_message(message.chat.id, status_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        await send_message(message.chat.id, "❌ Error getting bot status")

# Restart command handler (admin only)
@bot.message_handler(commands=["restart"])
async def handle_restart(message):
    """Restarts the bot (admin only)."""
    ADMIN_IDS = [message.chat.id]  # Add your admin chat IDs here
    
    if message.chat.id not in ADMIN_IDS:
        await send_message(message.chat.id, "⛔ This command is restricted to administrators.")
        return
        
    try:
        await send_message(message.chat.id, "🔄 Restarting bot...")
        logger.info("Bot restart initiated by admin")
        
        # Clear the download queue
        while not download_queue.empty():
            download_queue.get_nowait()
            download_queue.task_done()
            
        # Cleanup temporary files
        temp_dir = "downloads"  # Adjust to your temp directory
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                try:
                    os.remove(os.path.join(temp_dir, file))
                except Exception as e:
                    logger.error(f"Error cleaning up file {file}: {e}")
        
        # Restart the bot process
        os.execv(sys.executable, ['python'] + sys.argv)
    except Exception as e:
        logger.error(f"Error during restart: {e}")
        await send_message(message.chat.id, "❌ Restart failed")

# Stop command handler (admin only)
@bot.message_handler(commands=["stop"])
async def handle_stop(message):
    """Stops the bot (admin only)."""
    ADMIN_IDS = [message.chat.id]  # Add your admin chat IDs here
    
    if message.chat.id not in ADMIN_IDS:
        await send_message(message.chat.id, "⛔ This command is restricted to administrators.")
        return
        
    try:
        await send_message(message.chat.id, "🛑 Stopping bot...")
        logger.info("Bot stop initiated by admin")
        
        # Clear the download queue
        while not download_queue.empty():
            download_queue.get_nowait()
            download_queue.task_done()
            
        # Stop the bot
        await bot.stop_polling()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error during stop: {e}")
        await send_message(message.chat.id, "❌ Stop failed")

# Admin management commands
@bot.message_handler(commands=["addadmin"])
async def handle_add_admin(message):
    """Adds a new admin (super admin only)."""
    try:
        # Check if command sender is the default admin
        if message.from_user.id != DEFAULT_ADMIN:
            await send_message(message.chat.id, "⛔ This command is restricted to the super administrator.")
            return
            
        # Extract the user ID from the command
        parts = message.text.split()
        if len(parts) != 2:
            await send_message(
                message.chat.id,
                "⚠️ Please use the format: /addadmin <user_id>\n"
                "To get a user's ID, have them send /myid to the bot."
            )
            return
            
        try:
            new_admin_id = int(parts[1])
        except ValueError:
            await send_message(message.chat.id, "❌ Invalid user ID. Please provide a valid numeric ID.")
            return
            
        # Add the new admin ID to the config
        if new_admin_id not in ADMIN_IDS:
            ADMIN_IDS.append(new_admin_id)
            # Update the config file
            with open("config.py", "r") as f:
                lines = f.readlines()
            
            with open("config.py", "w") as f:
                admin_list_updated = False
                for line in lines:
                    if line.startswith("ADMIN_IDS = "):
                        f.write(f"ADMIN_IDS = {ADMIN_IDS}\n")
                        admin_list_updated = True
                    else:
                        f.write(line)
                
                if not admin_list_updated:
                    f.write(f"\nADMIN_IDS = {ADMIN_IDS}\n")
            
            await send_message(
                message.chat.id, 
                f"✅ Successfully added user ID {new_admin_id} as an admin."
            )
        else:
            await send_message(message.chat.id, "⚠️ This user is already an admin.")
            
    except Exception as e:
        logger.error(f"Error adding admin: {e}")
        await send_message(message.chat.id, "❌ Error adding admin")

@bot.message_handler(commands=["removeadmin"])
async def handle_remove_admin(message):
    """Removes an admin (super admin only)."""
    try:
        # Check if command sender is the default admin
        if message.from_user.id != DEFAULT_ADMIN:
            await send_message(message.chat.id, "⛔ This command is restricted to the super administrator.")
            return
            
        # Extract the user ID from the command
        parts = message.text.split()
        if len(parts) != 2:
            await send_message(
                message.chat.id,
                "⚠️ Please use the format: /removeadmin <user_id>"
            )
            return
            
        try:
            admin_id = int(parts[1])
        except ValueError:
            await send_message(message.chat.id, "❌ Invalid user ID. Please provide a valid numeric ID.")
            return
            
        # Prevent removing the default admin
        if admin_id == DEFAULT_ADMIN:
            await send_message(message.chat.id, "⛔ Cannot remove the super administrator.")
            return
            
        # Remove the admin ID from the config
        if admin_id in ADMIN_IDS:
            ADMIN_IDS.remove(admin_id)
            # Update the config file
            with open("config.py", "r") as f:
                lines = f.readlines()
            
            with open("config.py", "w") as f:
                for line in lines:
                    if line.startswith("ADMIN_IDS = "):
                        f.write(f"ADMIN_IDS = {ADMIN_IDS}\n")
                    else:
                        f.write(line)
            
            await send_message(
                message.chat.id,
                f"✅ Successfully removed user ID {admin_id} from admins."
            )
        else:
            await send_message(message.chat.id, "⚠️ This user is not an admin.")
            
    except Exception as e:
        logger.error(f"Error removing admin: {e}")
        await send_message(message.chat.id, "❌ Error removing admin")

@bot.message_handler(commands=["listadmins"])
async def handle_list_admins(message):
    """Lists all current admins."""
    try:
        # Check if command sender is an admin
        if message.from_user.id not in ADMIN_IDS:
            await send_message(message.chat.id, "⛔ This command is restricted to administrators.")
            return
            
        admin_list = "👥 **Current Administrators:**\n\n"
        for admin_id in ADMIN_IDS:
            admin_list += f"• `{admin_id}`"
            if admin_id == DEFAULT_ADMIN:
                admin_list += " (Super Admin)"
            admin_list += "\n"
            
        await bot.send_message(message.chat.id, admin_list, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Error listing admins: {e}")
        await send_message(message.chat.id, "❌ Error listing admins")

@bot.message_handler(commands=["myid"])
async def handle_myid(message):
    """Shows the user their Telegram ID."""
    try:
        await send_message(
            message.chat.id,
            f"🆔 Your Telegram ID is: `{message.from_user.id}`"
        )
    except Exception as e:
        logger.error(f"Error getting user ID: {e}")
        await send_message(message.chat.id, "❌ Error getting your ID")



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

