import os
import gc
import logging
import re
import time
import psutil
import asyncio
import queue
import threading

from datetime import datetime, timezone

from telebot import TeleBot

from config import (
    API_TOKEN,
    TELEGRAM_FILE_LIMIT,
)

# ============================================================
# LOCAL HANDLERS
# ============================================================

from handlers.youtube_handler import (
    process_youtube,
    extract_audio_ffmpeg
)

from handlers.instagram_handler import (
    process_instagram
)

from handlers.facebook_handlers import (
    process_facebook
)

from handlers.common_handler import (
    process_adult
)

from handlers.x_handler import (
    download_twitter_media
)

from handlers.trim_handlers import (
    process_video_trim,
    process_audio_trim
)

from utils.logger import setup_logging


# ============================================================
# CONSTANTS
# ============================================================

MAX_MEMORY_USAGE = 500 * 1024 * 1024
MAX_CONCURRENT_DOWNLOADS = 2
CLEANUP_INTERVAL = 300


# ============================================================
# LOGGING
# ============================================================

logger = setup_logging(logging.DEBUG)


# ============================================================
# TELEGRAM BOT
# ============================================================

bot = TeleBot(
    API_TOKEN,
    parse_mode="HTML"
)


# ============================================================
# QUEUE
# ============================================================

download_queue = queue.Queue()

download_semaphore = threading.Semaphore(
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

    return datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ============================================================
# MEMORY CHECK
# ============================================================

def check_memory_usage():

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
# ASYNC HANDLER RUNNER
# ============================================================

def run_async(function, *args):

    return asyncio.run(
        function(*args)
    )


# ============================================================
# CLEANUP
# ============================================================

def cleanup_files():

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

            time.sleep(
                CLEANUP_INTERVAL
            )

        except Exception as e:

            logger.error(
                f"[{get_current_utc()}] "
                f"Cleanup task error: {e}"
            )

            time.sleep(60)


# ============================================================
# SEND MESSAGE
# ============================================================

def send_message(chat_id, text):

    try:

        bot.send_message(
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

def process_download(
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

        if not check_memory_usage():

            send_message(
                message.chat.id,
                "⚠️ Server is currently under high load. "
                "Please try again later."
            )

            return

        active_downloads.add(
            download_id
        )

        with download_semaphore:

            request_type = "Video Download"

            if is_audio:

                request_type = "Audio Download"

            elif is_video_trim:

                request_type = "Video Trimming"

            elif is_audio_trim:

                request_type = "Audio Trimming"

            send_message(
                message.chat.id,
                f"📥 Processing your "
                f"{request_type.lower()}..."
            )

            platform = detect_platform(url)

            if not platform:

                send_message(
                    message.chat.id,
                    "⚠️ Unsupported URL."
                )

                return

            try:

                file_paths = []
                file_size = None

                if is_video_trim:

                    file_path, file_size = run_async(
                        process_video_trim,
                        url,
                        start_time,
                        end_time
                    )

                    if file_path:

                        file_paths = [
                            file_path
                        ]

                elif is_audio_trim:

                    file_path, file_size = run_async(
                        process_audio_trim,
                        url,
                        start_time,
                        end_time
                    )

                    if file_path:

                        file_paths = [
                            file_path
                        ]

                elif is_audio:

                    result = run_async(
                        extract_audio_ffmpeg,
                        url
                    )

                    if isinstance(result, tuple):

                        if result[0]:

                            file_paths = [
                                result[0]
                            ]

                        if len(result) > 1:

                            file_size = result[1]

                    elif result:

                        file_paths = [
                            result
                        ]

                else:

                    result = run_async(
                        PLATFORM_HANDLERS[platform],
                        url
                    )

                    if isinstance(result, tuple):

                        if isinstance(
                            result[0],
                            list
                        ):

                            file_paths = result[0]

                        elif result[0]:

                            file_paths = [
                                result[0]
                            ]

                        if len(result) > 1:

                            file_size = result[1]

                    elif result:

                        file_paths = [
                            result
                        ]

                if not file_paths:

                    send_message(
                        message.chat.id,
                        "❌ Download failed. "
                        "No media found."
                    )

                    return

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

                    actual_file_size = (
                        os.path.getsize(
                            file_path
                        )
                    )

                    if not file_size:

                        file_size = (
                            actual_file_size
                        )

                    if actual_file_size > TELEGRAM_FILE_LIMIT:

                        send_message(
                            message.chat.id,
                            "❌ File is too large "
                            "to send on Telegram."
                        )

                        logger.warning(
                            f"[{get_current_utc()}] "
                            f"File too large: "
                            f"{actual_file_size} bytes"
                        )

                    else:

                        try:

                            with open(
                                file_path,
                                "rb"
                            ) as file:

                                content = file.read()

                            if (
                                is_audio
                                or
                                is_audio_trim
                            ):

                                bot.send_audio(
                                    message.chat.id,
                                    content
                                )

                            else:

                                bot.send_video(
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

                            send_message(
                                message.chat.id,
                                "❌ Error sending file: "
                                f"{send_error}"
                            )

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

                send_message(
                    message.chat.id,
                    "❌ An error occurred: "
                    f"{process_error}"
                )

    except Exception as e:

        logger.error(
            f"[{get_current_utc()}] "
            f"Comprehensive error in "
            f"process_download: {e}",
            exc_info=True
        )

        send_message(
            message.chat.id,
            f"❌ An error occurred: {e}"
        )

    finally:

        active_downloads.discard(
            download_id
        )

        gc.collect()


# ============================================================
# DOWNLOAD WORKER
# ============================================================

def worker():

    while True:

        task = download_queue.get()

        try:

            (
                message,
                url,
                is_audio,
                is_video_trim,
                is_audio_trim,
                start_time,
                end_time
            ) = task

            process_download(
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

                send_message(
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
def send_welcome(message):

    welcome_text = (
        "🤖 Media Download Bot 🤖\n\n"

        "I can help you download video/audio "
        "from various platforms:\n\n"

        "• YouTube\n"
        "• Instagram\n"
        "• Facebook\n"
        "• Twitter/X\n\n"

        "Commands:\n\n"

        "• Send a direct URL to download video\n"
        "• /audio <URL> - Extract full audio\n"
        "• /trim <URL> <Start Time> <End Time> "
        "- Trim video segment\n"
        "• /trimAudio <URL> <Start Time> <End Time> "
        "- Extract audio segment\n\n"

        "Examples:\n\n"

        "• /audio https://youtube.com/watch?v=example\n\n"

        "• /trim https://youtube.com/watch?v=example "
        "00:01:00 00:02:30\n\n"

        "• /trimAudio https://youtube.com/watch?v=example "
        "00:01:00 00:02:30"
    )

    bot.send_message(
        message.chat.id,
        welcome_text
    )


# ============================================================
# AUDIO COMMAND
# ============================================================

@bot.message_handler(
    commands=["audio"]
)
def handle_audio_request(message):

    url = (
        message.text
        .replace("/audio", "", 1)
        .strip()
    )

    if not url:

        send_message(
            message.chat.id,
            "⚠️ Please provide a URL."
        )

        return

    download_queue.put(
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

    send_message(
        message.chat.id,
        "🎵 Added to audio extraction queue!"
    )


# ============================================================
# VIDEO TRIM
# ============================================================

@bot.message_handler(
    commands=["trim"]
)
def handle_video_trim_request(message):

    match = re.search(
        r"(https?://[^\s]+)\s+"
        r"(\d{1,2}:\d{2}:\d{2})\s+"
        r"(\d{1,2}:\d{2}:\d{2})",
        message.text
    )

    if not match:

        send_message(
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

    download_queue.put(
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

    send_message(
        message.chat.id,
        "✂️🎬 Added to video trimming queue!"
    )


# ============================================================
# AUDIO TRIM
# ============================================================

@bot.message_handler(
    commands=["trimAudio"]
)
def handle_audio_trim_request(message):

    match = re.search(
        r"(https?://[^\s]+)\s+"
        r"(\d{1,2}:\d{2}:\d{2})\s+"
        r"(\d{1,2}:\d{2}:\d{2})",
        message.text
    )

    if not match:

        send_message(
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

    download_queue.put(
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

    send_message(
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
def handle_message(message):

    url = message.text.strip()

    download_queue.put(
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

    send_message(
        message.chat.id,
        "🎬 Added to video download queue!"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    logger.info(
        f"[{get_current_utc()}] "
        "Starting Media Download Bot..."
    )

    # In bot.py, replace your current main() with this:

def start_background_tasks():
    logger.info(f"[{get_current_utc()}] Starting background tasks...")
    
    logger.info("Using manual Instagram cookies from cookies/instagram_cookies.txt when needed.")
    threading.Thread(target=cleanup_files, daemon=True).start()

    num_workers = min(3, os.cpu_count() or 1)
    logger.info(f"[{get_current_utc()}] Starting {num_workers} workers...")

    for _ in range(num_workers):
        threading.Thread(target=worker, daemon=True).start()
        
    # DO NOT put bot.infinity_polling() here. Webhooks replace polling.

