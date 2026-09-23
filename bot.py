import os
import gc
import logging
import re
import time
import asyncio
from datetime import datetime, timezone

from telebot import types
from telebot.async_telebot import AsyncTeleBot

from config import API_TOKEN, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import process_video_trim, process_audio_trim
from utils.logger import setup_logging

MAX_MEMORY_USAGE = 500 * 1024 * 1024
MAX_CONCURRENT_DOWNLOADS = 2
CLEANUP_INTERVAL = 300

logger = setup_logging(logging.DEBUG)

bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")

download_queue = asyncio.Queue()
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
active_downloads = set()

PLATFORM_PATTERNS = {
    "YouTube": re.compile(r"(youtube\.com|youtu\.be)", re.IGNORECASE),
    "Instagram": re.compile(r"instagram\.com", re.IGNORECASE),
    "Facebook": re.compile(r"facebook\.com", re.IGNORECASE),
    "Twitter/X": re.compile(r"(x\.com|twitter\.com)", re.IGNORECASE),
    "Adult": re.compile(
        r"(pornhub\.com|xvideos\.com|redtube\.com|xhamster\.com|xnxx\.com)",
        re.IGNORECASE,
    ),
}

PLATFORM_HANDLERS = {
    "YouTube": process_youtube,
    "Instagram": process_instagram,
    "Facebook": process_facebook,
    "Twitter/X": download_twitter_media,
    "Adult": process_adult,
}


def get_current_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def check_memory_usage():
    try:
        import psutil
        memory_usage = psutil.Process(os.getpid()).memory_info().rss
        logger.debug(
            "[%s] Current memory usage: %.2f MB",
            get_current_utc(),
            memory_usage / 1024 / 1024,
        )
        return memory_usage < MAX_MEMORY_USAGE
    except Exception as e:
        logger.error("Memory check error: %s", e)
        return True


async def send_message(chat_id, text):
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error("Error sending message: %s", e, exc_info=True)


def detect_platform(url):
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None


async def run_blocking(function, *args):
    """Run existing synchronous download/FFmpeg code outside the event loop."""
    return await asyncio.to_thread(function, *args)


async def process_download(
    message,
    url,
    is_audio=False,
    is_video_trim=False,
    is_audio_trim=False,
    start_time=None,
    end_time=None,
):
    download_id = f"{message.chat.id}_{time.time_ns()}"

    try:
        if not check_memory_usage():
            await send_message(
                message.chat.id,
                "⚠️ Server is currently under high load. Please try again later.",
            )
            return

        active_downloads.add(download_id)

        async with download_semaphore:
            if is_audio:
                request_type = "Audio Download"
            elif is_video_trim:
                request_type = "Video Trimming"
            elif is_audio_trim:
                request_type = "Audio Trimming"
            else:
                request_type = "Video Download"

            await send_message(
                message.chat.id,
                f"📥 Processing your {request_type.lower()}...",
            )

            platform = detect_platform(url)
            if not platform:
                await send_message(message.chat.id, "⚠️ Unsupported URL.")
                return

            file_paths = []
            file_size = None

            if is_video_trim:
                result = await run_blocking(
                    process_video_trim, url, start_time, end_time
                )
            elif is_audio_trim:
                result = await run_blocking(
                    process_audio_trim, url, start_time, end_time
                )
            elif is_audio:
                result = await run_blocking(extract_audio_ffmpeg, url)
            else:
                result = await run_blocking(PLATFORM_HANDLERS[platform], url)

            if isinstance(result, tuple):
                first = result[0] if result else None
                file_size = result[1] if len(result) > 1 else None

                if isinstance(first, list):
                    file_paths = first
                elif first:
                    file_paths = [first]
            elif result:
                file_paths = [result]

            if not file_paths:
                await send_message(
                    message.chat.id,
                    "❌ Download failed. No media found.",
                )
                return

            for file_path in file_paths:
                if not file_path or not os.path.exists(file_path):
                    logger.warning("File does not exist: %s", file_path)
                    continue

                actual_file_size = os.path.getsize(file_path)

                if actual_file_size > TELEGRAM_FILE_LIMIT:
                    await send_message(
                        message.chat.id,
                        "❌ File is too large to send on Telegram.",
                    )
                    continue

                try:
                    telegram_file = types.InputFile(file_path)

                    if is_audio or is_audio_trim:
                        await bot.send_audio(
                            message.chat.id,
                            telegram_file,
                        )
                    else:
                        await bot.send_video(
                            message.chat.id,
                            telegram_file,
                            supports_streaming=True,
                        )

                    logger.info("Successfully sent: %s", file_path)

                except Exception as send_error:
                    logger.error(
                        "Error sending file: %s",
                        send_error,
                        exc_info=True,
                    )
                    await send_message(
                        message.chat.id,
                        f"❌ Error sending file: {send_error}",
                    )
                finally:
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception as cleanup_error:
                        logger.error(
                            "Cleanup error for %s: %s",
                            file_path,
                            cleanup_error,
                        )

    except Exception as e:
        logger.error(
            "Processing error: %s",
            e,
            exc_info=True,
        )
        await send_message(message.chat.id, f"❌ An error occurred: {e}")

    finally:
        active_downloads.discard(download_id)
        gc.collect()


async def worker():
    while True:
        task = await download_queue.get()
        try:
            await process_download(*task)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Worker error: %s", e, exc_info=True)
            try:
                await send_message(task[0].chat.id, f"❌ Worker error: {e}")
            except Exception:
                pass
        finally:
            download_queue.task_done()


async def cleanup_files():
    while True:
        try:
            temp_dir = "downloads"
            if os.path.exists(temp_dir):
                now = time.time()

                for filename in os.listdir(temp_dir):
                    filepath = os.path.join(temp_dir, filename)

                    try:
                        if (
                            os.path.isfile(filepath)
                            and now - os.path.getctime(filepath) > 3600
                        ):
                            os.remove(filepath)
                            logger.info("Removed old file: %s", filepath)
                    except Exception as e:
                        logger.error(
                            "Error cleaning file %s: %s",
                            filepath,
                            e,
                        )

            gc.collect()
            await asyncio.sleep(CLEANUP_INTERVAL)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Cleanup task error: %s", e, exc_info=True)
            await asyncio.sleep(60)


async def start_background_tasks():
    logger.info("Starting async background tasks...")
    tasks = [
        asyncio.create_task(cleanup_files(), name="cleanup"),
    ]

    worker_count = min(3, os.cpu_count() or 1)
    logger.info("Starting %s async workers...", worker_count)

    for index in range(worker_count):
        tasks.append(
            asyncio.create_task(worker(), name=f"download-worker-{index + 1}")
        )

    return tasks


@bot.message_handler(commands=["start", "help"])
async def send_welcome(message):
    welcome_text = (
        "🤖 Media Download Bot 🤖\n\n"
        "I can help you download video/audio from various platforms:\n\n"
        "• YouTube\n"
        "• Instagram\n"
        "• Facebook\n"
        "• Twitter/X\n\n"
        "Commands:\n\n"
        "• Send a direct URL to download video\n"
        "• /audio <URL> - Extract full audio\n"
        "• /trim <URL> <Start Time> <End Time> - Trim video\n"
        "• /trimAudio <URL> <Start Time> <End Time> - Extract audio segment"
    )
    await bot.send_message(message.chat.id, welcome_text)


@bot.message_handler(commands=["audio"])
async def handle_audio_request(message):
    url = message.text.replace("/audio", "", 1).strip()

    if not url:
        await send_message(message.chat.id, "⚠️ Please provide a URL.")
        return

    await download_queue.put(
        (message, url, True, False, False, None, None)
    )
    await send_message(message.chat.id, "🎵 Added to audio extraction queue!")


@bot.message_handler(commands=["trim"])
async def handle_video_trim_request(message):
    match = re.search(
        r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})",
        message.text,
    )

    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format.\nUse: /trim <URL> <Start Time> <End Time>",
        )
        return

    url, start_time, end_time = match.groups()

    await download_queue.put(
        (message, url, False, True, False, start_time, end_time)
    )
    await send_message(message.chat.id, "✂️🎬 Added to video trimming queue!")


@bot.message_handler(commands=["trimAudio"])
async def handle_audio_trim_request(message):
    match = re.search(
        r"(https?://[^\s]+)\s+(\d{1,2}:\d{2}:\d{2})\s+(\d{1,2}:\d{2}:\d{2})",
        message.text,
    )

    if not match:
        await send_message(
            message.chat.id,
            "⚠️ Invalid format.\nUse: /trimAudio <URL> <Start Time> <End Time>",
        )
        return

    url, start_time, end_time = match.groups()

    await download_queue.put(
        (message, url, False, False, True, start_time, end_time)
    )
    await send_message(
        message.chat.id,
        "✂️🎵 Added to audio segment extraction queue!",
    )


@bot.message_handler(
    func=lambda message: True,
    content_types=["text"],
)
async def handle_message(message):
    url = message.text.strip()

    await download_queue.put(
        (message, url, False, False, False, None, None)
    )
    await send_message(
        message.chat.id,
        "🎬 Added to video download queue!",
    )
