import os
import gc
import logging
import asyncio
import aiofiles
import re
import time
import psutil
from datetime import datetime, timezone
from asyncio import Semaphore

from telebot.async_telebot import AsyncTeleBot

from config import (
    API_TOKEN,
    TELEGRAM_FILE_LIMIT,
)

# Import local modules
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import process_video_trim, process_audio_trim
from handlers.image_handlers import process_instagram_image

from utils.logger import setup_logging
from utils.instagram_cookies import auto_refresh_cookies


# ============================================================
# CONSTANTS
# ============================================================

MAX_MEMORY_USAGE = 500 * 1024 * 1024  # 500 MB
MAX_CONCURRENT_DOWNLOADS = 2
CLEANUP_INTERVAL = 300  # 5 minutes


# ============================================================
# LOGGING
# ============================================================

logger = setup_logging(logging.DEBUG)


# ============================================================
# TELEGRAM BOT
# ============================================================

bot = AsyncTeleBot(
    API_TOKEN,
    parse_mode="HTML"
)


# ============================================================
# QUEUE / SEMAPHORE
# ============================================================

download_queue = asyncio.Queue()

download_semaphore = Semaphore(
    MAX_CONCURRENT_DOWNLOADS
)


# ============================================================
# ACTIVE DOWNLOAD TRACKING
# ============================================================

active_downloads = set()


# ============================================================
# PLATFORM PATTERNS
# ============================================================

PLATFORM_PATTERNS = {

    "YouTube": re.compile(
        r"(youtube\.com|youtu\.be)",
        re.IGNORECASE
    ),

    "Instagram": re.compile(
        r"instagram\.com",
        re.IGNORECASE
    ),

    "Facebook": re.compile(
        r"facebook\.com",
        re.IGNORECASE
    ),

    "Twitter/X": re.compile(
        r"(x\.com|twitter\.com)",
        re.IGNORECASE
    ),

    "Adult": re.compile(
        r"(pornhub\.com|xvideos\.com|redtube\.com|"
        r"xhamster\.com|xnxx\.com)",
        re.IGNORECASE
    ),
}


# ============================================================
# PLATFORM HANDLERS
# ============================================================

PLATFORM_HANDLERS = {

    "YouTube": process_youtube,

    "Instagram": process_instagram,

    "Facebook": process_facebook,

    "Twitter/X": download_twitter_media,

    "Adult": process_adult,
}


# ============================================================
# UTC TIME
# ============================================================

def get_current_utc():
    """
    Returns current UTC time.
    """

    return datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ============================================================
# MEMORY CHECK
# ============================================================

async def check_memory_usage():
    """
    Checks current process memory usage.
    """

    try:

        process = psutil.Process(
            os.getpid()
        )

        memory_usage = process.memory_info().rss

        logger.debug(
            f"[{get_current_utc()}] "
            f"Current memory usage: "
            f"{memory_usage / 1024 / 1024:.2f} MB"
        )

        return memory_usage < MAX_MEMORY_USAGE

    except Exception as e:

        logger.error(
            f"[{get_current_utc()}] "
            f"Memory check error: {e}"
        )

        return True


# ============================================================
# CLEANUP FILES
# ============================================================

async def cleanup_files():

    while True:

        try:

            temp_dir = "downloads"

            if os.path.exists(temp_dir):

                for filename in os.listdir(temp_dir):

                    filepath = os.path.join(
                        temp_dir,
                        filename
                    )

                    try:

                        if (
                            os.path.isfile(filepath)
                            and
                            time.time()
                            - os.path.getctime(filepath)
                            > 3600
                        ):

                            os.remove(filepath)

                            logger.info(
                                f"[{get_current_utc()}] "
                                f"Removed old file: "
                                f"{filepath}"
                            )

                    except Exception as e:

                        logger.error(
                            f"[{get_current_utc()}] "
                            f"Error cleaning file "
                            f"{filepath}: {e}"
                        )

            gc.collect()

            await asyncio.sleep(
                CLEANUP_INTERVAL
            )

        except Exception as e:

            logger.error(
                f"[{get_current_utc()}] "
                f"Cleanup task error: {e}"
            )

            await asyncio.sleep(60)


# ============================================================
# SEND MESSAGE
# ============================================================

async def send_message(chat_id, text):

    try:

        await bot.send_message(
            chat_id,
            text
        )

    except Exception as e:

        logger.error(
            f"[{get_current_utc()}] "
            f"Error sending message: {e}"
        )


# ============================================================
# PLATFORM DETECTION
# ============================================================

def detect_platform(url):

    for platform, pattern in PLATFORM_PATTERNS.items():

        if pattern.search(url):

            return platform

    return None


# ============================================================
# PROCESS DOWNLOAD
# ============================================================

async def process_download(
    message,
    url,
    is_audio=False,
    is_video_trim=False,
    is_audio_trim=False,
    start_time=None,
    end_time=None
):

    download_id = (
        f"{message.chat.id}_{int(time.time())}"
    )

    try:

        # ----------------------------------------------------
        # MEMORY CHECK
        # ----------------------------------------------------

        if not await check_memory_usage():

            await send_message(
                message.chat.id,
                "⚠️ Server is currently under high load. "
                "Please try again later."
            )

            return

        # ----------------------------------------------------
        # ACTIVE DOWNLOAD
        # ----------------------------------------------------

        active_downloads.add(
            download_id
        )

        # ----------------------------------------------------
        # SEMAPHORE
        # ----------------------------------------------------

        async with download_semaphore:

            request_type = "Video Download"

            if is_audio:

                request_type = "Audio Download"

            elif is_video_trim:

                request_type = "Video Trimming"

            elif is_audio_trim:

                request_type = "Audio Trimming"

            await send_message(
                message.chat.id,
                f"📥 Processing your "
                f"{request_type.lower()}..."
            )

            # ------------------------------------------------
            # DETECT PLATFORM
            # ------------------------------------------------

            platform = detect_platform(url)

            if not platform:

                await send_message(
                    message.chat.id,
                    "⚠️ Unsupported URL."
                )

                return

            # ------------------------------------------------
            # PROCESS
            # ------------------------------------------------

            try:

                file_paths = []
                file_size = None

                # ============================================
                # VIDEO TRIM
                # ============================================

                if is_video_trim:

                    file_path, file_size = (
                        await process_video_trim(
                            url,
                            start_time,
                            end_time
                        )
                    )

                    if file_path:

                        file_paths = [
                            file_path
                        ]

                # ============================================
                # AUDIO TRIM
                # ============================================

                elif is_audio_trim:

                    file_path, file_size = (
                        await process_audio_trim(
                            url,
                            start_time,
                            end_time
                        )
                    )

                    if file_path:

                        file_paths = [
                            file_path
                        ]

                # ============================================
                # AUDIO EXTRACTION
                # ============================================

                elif is_audio:

                    result = (
                        await extract_audio_ffmpeg(
                            url
                        )
                    )

                    if isinstance(result, tuple):

                        if result[0]:

                            file_paths = [
                                result[0]
                            ]

                        if len(result) > 1:

                            file_size = result[1]

                    else:

                        if result:

                            file_paths = [
                                result
                            ]

                # ============================================
                # NORMAL DOWNLOAD
                # ============================================

                else:

                    result = (
                        await PLATFORM_HANDLERS[
                            platform
                        ](url)
                    )

                    if isinstance(result, tuple):

                        if isinstance(
                            result[0],
                            list
                        ):

                            file_paths = (
                                result[0]
                            )

                        elif result[0]:

                            file_paths = [
                                result[0]
                            ]

                        if len(result) > 1:

                            file_size = result[1]

                    else:

                        if result:

                            file_paths = [
                                result
                            ]

                # ------------------------------------------------
                # NO FILE
                # ------------------------------------------------

                if not file_paths:

                    await send_message(
                        message.chat.id,
                        "❌ Download failed. "
                        "No media found."
                    )

                    return

                # ------------------------------------------------
                # PROCESS EACH FILE
                # ------------------------------------------------

                for file_path in file_paths:

                    if (
                        not file_path
                        or
                        not os.path.exists(
                            file_path
                        )
                    ):

                        logger.warning(
                            f"File does not exist: "
                            f"{file_path}"
                        )

                        continue

                    # Get actual file size
                    actual_file_size = (
                        os.path.getsize(
                            file_path
                        )
                    )

                    if not file_size:

                        file_size = (
                            actual_file_size
                        )

                    # ============================================
                    # TELEGRAM FILE SIZE CHECK
                    # ============================================

                    if actual_file_size > TELEGRAM_FILE_LIMIT:

                        await send_message(
                            message.chat.id,
                            "❌ File is too large "
                            "to send on Telegram."
                        )

                        logger.warning(
                            f"[{get_current_utc()}] "
                            f"File too large: "
                            f"{actual_file_size} bytes"
                        )

                    # ============================================
                    # SEND FILE TO TELEGRAM
                    # ============================================

                    else:

                        try:

                            async with aiofiles.open(
                                file_path,
                                "rb"
                            ) as file:

                                content = (
                                    await file.read()
                                )

                            # ------------------------------------
                            # AUDIO
                            # ------------------------------------

                            if (
                                is_audio
                                or
                                is_audio_trim
                            ):

                                await bot.send_audio(
                                    message.chat.id,
                                    content
                                )

                            # ------------------------------------
                            # VIDEO
                            # ------------------------------------

                            else:

                                await bot.send_video(
                                    message.chat.id,
                                    content,
                                    supports_streaming=True
                                )

                            logger.info(
                                f"[{get_current_utc()}] "
                                f"Successfully sent: "
                                f"{file_path}"
                            )

                        except Exception as send_error:

                            logger.error(
                                f"[{get_current_utc()}] "
                                f"Error sending file: "
                                f"{send_error}",
                                exc_info=True
                            )

                            await send_message(
                                message.chat.id,
                                f"❌ Error sending file: "
                                f"{send_error}"
                            )

                    # ============================================
                    # CLEANUP FILE
                    # ============================================

                    try:

                        if os.path.exists(
                            file_path
                        ):

                            os.remove(
                                file_path
                            )

                            logger.info(
                                f"[{get_current_utc()}] "
                                f"Cleaned up: "
                                f"{file_path}"
                            )

                    except Exception as cleanup_error:

                        logger.error(
                            f"[{get_current_utc()}] "
                            f"Cleanup error: "
                            f"{cleanup_error}"
                        )

            except Exception as process_error:

                logger.error(
                    f"[{get_current_utc()}] "
                    f"Processing error: "
                    f"{process_error}",
                    exc_info=True
                )

                await send_message(
                    message.chat.id,
                    f"❌ An error occurred: "
                    f"{process_error}"
                )

    except Exception as e:

        logger.error(
            f"[{get_current_utc()}] "
            f"Comprehensive error in "
            f"process_download: {e}",
            exc_info=True
        )

        await send_message(
            message.chat.id,
            f"❌ An error occurred: {e}"
        )

    finally:

        active_downloads.discard(
            download_id
        )

        gc.collect()


# ============================================================
# INSTAGRAM IMAGE DOWNLOAD
# ============================================================

async def process_image_download(
    message,
    url
):

    try:

        await send_message(
            message.chat.id,
            "🖼️ Processing Instagram image..."
        )

        logger.info(
            f"Processing Instagram image URL: {url}"
        )

        try:

            result = (
                await process_instagram_image(
                    url
                )
            )

            # ----------------------------------------------
            # RETURN FORMAT
            # ----------------------------------------------

            if isinstance(result, list):

                file_paths = result

            elif (
                isinstance(result, tuple)
                and
                len(result) >= 2
            ):

                file_paths = (
                    result[0]
                    if isinstance(
                        result[0],
                        list
                    )
                    else [result[0]]
                )

            else:

                file_paths = (
                    [result]
                    if result
                    else []
                )

            # ----------------------------------------------
            # NO FILE
            # ----------------------------------------------

            if (
                not file_paths
                or
                all(
                    not path
                    for path in file_paths
                )
            ):

                logger.warning(
                    "No valid image paths returned"
                )

                await send_message(
                    message.chat.id,
                    "❌ Download failed. "
                    "No images found."
                )

                return

            # ----------------------------------------------
            # PROCESS IMAGES
            # ----------------------------------------------

            success_count = 0

            for file_path in file_paths:

                if (
                    not file_path
                    or
                    not os.path.exists(
                        file_path
                    )
                ):

                    logger.warning(
                        f"Image path does not exist: "
                        f"{file_path}"
                    )

                    continue

                file_size = (
                    os.path.getsize(
                        file_path
                    )
                )

                # ------------------------------------------
                # FILE TOO LARGE
                # ------------------------------------------

                if file_size > TELEGRAM_FILE_LIMIT:

                    await send_message(
                        message.chat.id,
                        "❌ Image is too large "
                        "to send on Telegram."
                    )

                # ------------------------------------------
                # SEND IMAGE
                # ------------------------------------------

                else:

                    try:

                        async with aiofiles.open(
                            file_path,
                            "rb"
                        ) as file:

                            file_content = (
                                await file.read()
                            )

                        await bot.send_photo(
                            message.chat.id,
                            file_content,
                            timeout=60
                        )

                        success_count += 1

                        logger.info(
                            "Successfully sent image"
                        )

                    except Exception as send_error:

                        logger.error(
                            f"Error sending image: "
                            f"{send_error}",
                            exc_info=True
                        )

                        await send_message(
                            message.chat.id,
                            f"❌ Error sending image: "
                            f"{send_error}"
                        )

                # ------------------------------------------
                # CLEANUP
                # ------------------------------------------

                try:

                    if os.path.exists(
                        file_path
                    ):

                        os.remove(
                            file_path
                        )

                except Exception as cleanup_error:

                    logger.error(
                        f"Failed to cleanup image: "
                        f"{cleanup_error}"
                    )

            # ----------------------------------------------
            # SUCCESS
            # ----------------------------------------------

            if success_count > 0:

                await send_message(
                    message.chat.id,
                    f"✅ {success_count} "
                    f"Instagram image(s) downloaded "
                    f"successfully!"
                )

        except Exception as e:

            logger.error(
                f"Error processing Instagram image: "
                f"{e}",
                exc_info=True
            )

            await send_message(
                message.chat.id,
                f"❌ An error occurred: {e}"
            )

    except Exception as e:

        logger.error(
            f"Comprehensive error in "
            f"process_image_download: {e}",
            exc_info=True
        )

        await send_message(
            message.chat.id,
            f"❌ An error occurred: {e}"
        )


# ============================================================
# DOWNLOAD WORKER
# ============================================================

async def worker():

    while True:

        task = await download_queue.get()

        try:

            # ================================================
            # IMAGE TASK
            # ================================================

            if len(task) == 2:

                message, url = task

                await process_image_download(
                    message,
                    url
                )

            # ================================================
            # NORMAL TASK
            # ================================================

            else:

                (
                    message,
                    url,
                    is_audio,
                    is_video_trim,
                    is_audio_trim,
                    start_time,
                    end_time
                ) = task

                await process_download(
                    message,
                    url,
                    is_audio,
                    is_video_trim,
                    is_audio_trim,
                    start_time,
                    end_time
                )

        except Exception as e:

            logger.error(
                f"[{get_current_utc()}] "
                f"Worker error: {e}",
                exc_info=True
            )

            try:

                await send_message(
                    task[0].chat.id,
                    f"❌ Worker error: {e}"
                )

            except Exception:
                pass

        finally:

            download_queue.task_done()

            gc.collect()


# ============================================================
# START / HELP
# ============================================================

@bot.message_handler(
    commands=["start", "help"]
)
async def send_welcome(message):

    welcome_text = (
        "🤖 Media Download Bot 🤖\n\n"

        "I can help you download media "
        "from various platforms:\n"

        "• YouTube\n"
        "• Instagram\n"
        "• Facebook\n"
        "• Twitter/X\n\n"

        "Commands:\n"

        "• Send a direct URL to download video\n"
        "• /audio <URL> - Extract full audio\n"
        "• /image <URL> - Download Instagram images\n"
        "• /trim <URL> <Start Time> <End Time> "
        "- Trim video segment\n"
        "• /trimAudio <URL> <Start Time> <End Time> "
        "- Extract audio segment\n\n"

        "Examples:\n"

        "• /image https://instagram.com/p/example\n"

        "• /trim https://youtube.com/watch?v=example "
        "00:01:00 00:02:30\n"

        "• /trimAudio https://youtube.com/watch?v=example "
        "00:01:00 00:02:30"
    )

    await bot.send_message(
        message.chat.id,
        welcome_text
    )


# ============================================================
# INSTAGRAM STORY
# ============================================================

@bot.message_handler(
    commands=["story"]
)
async def handle_story_request(message):

    url = (
        message.text
        .replace("/story", "", 1)
        .strip()
    )

    if not url:

        await send_message(
            message.chat.id,
            "⚠️ Please provide an Instagram story URL."
        )

        return

    if (
        "/stories/" not in url
        or
        not PLATFORM_PATTERNS[
            "Instagram"
        ].search(url)
    ):

        await send_message(
            message.chat.id,
            "⚠️ Please provide a valid Instagram story URL."
        )

        return

    await send_message(
        message.chat.id,
        "📲 Instagram story detected! "
        "Fetching image(s)..."
    )

    await download_queue.put(
        (
            message,
            url
        )
    )


# ============================================================
# AUDIO COMMAND
# ============================================================

@bot.message_handler(
    commands=["audio"]
)
async def handle_audio_request(message):

    url = (
        message.text
        .replace("/audio", "", 1)
        .strip()
    )

    if not url:

        await send_message(
            message.chat.id,
            "⚠️ Please provide a URL."
        )

        return

    await download_queue.put(
        (
            message,
            url,
            True,
            False,
            False,
            None,
            None
        )
    )

    await send_message(
        message.chat.id,
        "🎵 Added to audio extraction queue!"
    )


# ============================================================
# INSTAGRAM IMAGE COMMAND
# ============================================================

@bot.message_handler(
    commands=["image"]
)
async def handle_image_request(message):

    url = (
        message.text
        .replace("/image", "", 1)
        .strip()
    )

    if not url:

        await send_message(
            message.chat.id,
            "⚠️ Please provide an Instagram image URL."
        )

        return

    if not PLATFORM_PATTERNS[
        "Instagram"
    ].search(url):

        await send_message(
            message.chat.id,
            "⚠️ This command only works "
            "with Instagram image URLs."
        )

        return

    await download_queue.put(
        (
            message,
            url
        )
    )

    await send_message(
        message.chat.id,
        "🖼️ Added to image download queue!"
    )


# ============================================================
# VIDEO TRIM
# ============================================================

@bot.message_handler(
    commands=["trim"]
)
async def handle_video_trim_request(message):

    match = re.search(
        r"(https?://[^\s]+)\s+"
        r"(\d{1,2}:\d{2}:\d{2})\s+"
        r"(\d{1,2}:\d{2}:\d{2})",
        message.text
    )

    if not match:

        await send_message(
            message.chat.id,
            "⚠️ Invalid format.\n\n"
            "Use:\n"
            "/trim <URL> "
            "<Start Time> "
            "<End Time>\n\n"
            "Example:\n"
            "/trim https://youtube.com/watch?v=example "
            "00:01:00 00:02:30"
        )

        return

    url, start_time, end_time = (
        match.groups()
    )

    await download_queue.put(
        (
            message,
            url,
            False,
            True,
            False,
            start_time,
            end_time
        )
    )

    await send_message(
        message.chat.id,
        "✂️🎬 Added to video trimming queue!"
    )


# ============================================================
# AUDIO TRIM
# ============================================================

@bot.message_handler(
    commands=["trimAudio"]
)
async def handle_audio_trim_request(message):

    match = re.search(
        r"(https?://[^\s]+)\s+"
        r"(\d{1,2}:\d{2}:\d{2})\s+"
        r"(\d{1,2}:\d{2}:\d{2})",
        message.text
    )

    if not match:

        await send_message(
            message.chat.id,
            "⚠️ Invalid format.\n\n"
            "Use:\n"
            "/trimAudio <URL> "
            "<Start Time> "
            "<End Time>\n\n"
            "Example:\n"
            "/trimAudio https://youtube.com/watch?v=example "
            "00:01:00 00:02:30"
        )

        return

    url, start_time, end_time = (
        match.groups()
    )

    await download_queue.put(
        (
            message,
            url,
            False,
            False,
            True,
            start_time,
            end_time
        )
    )

    await send_message(
        message.chat.id,
        "✂️🎵 Added to audio segment extraction queue!"
    )


# ============================================================
# GENERAL MESSAGE HANDLER
# ============================================================

@bot.message_handler(
    func=lambda message: True,
    content_types=["text"]
)
async def handle_message(message):

    url = message.text.strip()

    await download_queue.put(
        (
            message,
            url,
            False,
            False,
            False,
            None,
            None
        )
    )

    await send_message(
        message.chat.id,
        "🎬 Added to video download queue!"
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    logger.info(
        f"[{get_current_utc()}] "
        "Starting Media Download Bot..."
    )

    # ----------------------------------------------
    # Instagram cookie refresh
    # ----------------------------------------------

    asyncio.create_task(
        auto_refresh_cookies()
    )

    # ----------------------------------------------
    # Cleanup task
    # ----------------------------------------------

    asyncio.create_task(
        cleanup_files()
    )

    # ----------------------------------------------
    # Workers
    # ----------------------------------------------

    num_workers = min(
        3,
        os.cpu_count() or 1
    )

    logger.info(
        f"[{get_current_utc()}] "
        f"Starting {num_workers} workers..."
    )

    for _ in range(num_workers):

        asyncio.create_task(
            worker()
        )

    # ----------------------------------------------
    # Start polling
    # ----------------------------------------------

    logger.info(
        f"[{get_current_utc()}] "
        "Bot polling started."
    )

    await bot.polling(
        non_stop=True
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        logger.info(
            "Bot stopped by user."
        )

    except Exception as e:

        logger.error(
            f"Fatal error: {e}",
            exc_info=True
        )