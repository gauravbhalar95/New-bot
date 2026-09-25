import os
import gc
import logging
import re
import time
import asyncio
import subprocess
from html import escape
from datetime import datetime, timezone

from telebot import types
from telebot.async_telebot import AsyncTeleBot

from config import API_TOKEN, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import process_instagram
from handlers.threads_handler import process_threads
from handlers.facebook_handlers import process_facebook
from handlers.common_handler import process_adult
from handlers.x_handler import download_twitter_media
from handlers.trim_handlers import process_video_trim, process_audio_trim
from utils.logger import setup_logging

MAX_MEMORY_USAGE = 500 * 1024 * 1024
MAX_CONCURRENT_DOWNLOADS = 2
CLEANUP_INTERVAL = 300
MAX_DOWNLOAD_RETRIES = 3
PROGRESS_INTERVAL = 5
SPLIT_TARGET_RATIO = 0.90

logger = setup_logging(logging.DEBUG)

bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")

download_queue = asyncio.Queue()
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
active_downloads = set()
active_tasks = {}
cancelled_downloads = set()

PLATFORM_PATTERNS = {
    "YouTube": re.compile(r"(youtube\.com|youtu\.be)", re.IGNORECASE),
    "Instagram": re.compile(r"instagram\.com", re.IGNORECASE),
    "Threads": re.compile(r"(threads\.net|threads\.com)", re.IGNORECASE),
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
    "Threads": process_threads,
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
        return await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error("Error sending message: %s", e, exc_info=True)
        return None


def detect_platform(url):
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None


async def run_blocking(function, *args):
    return await asyncio.to_thread(function, *args)


def split_large_file(file_path):
    """Split a large media file into Telegram-sized chunks without re-encoding."""
    file_size = os.path.getsize(file_path)
    target_size = int(TELEGRAM_FILE_LIMIT * SPLIT_TARGET_RATIO)

    if file_size <= TELEGRAM_FILE_LIMIT:
        return [file_path]

    base, ext = os.path.splitext(file_path)
    output_pattern = f"{base}.part%03d{ext}"

    # Estimate segment duration from the file size. We then verify each
    # segment and retry with a smaller duration if necessary.
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    duration = float(probe.stdout.strip()) if probe.returncode == 0 and probe.stdout.strip() else 0
    if duration <= 0:
        raise RuntimeError("Cannot determine media duration for file splitting")

    seconds = max(10, int(duration * target_size / file_size))

    for attempt in range(1, 6):
        for old in list(os.path.dirname(file_path) and os.listdir(os.path.dirname(file_path)) or []):
            if old.startswith(os.path.basename(base) + ".part"):
                try:
                    os.remove(os.path.join(os.path.dirname(file_path), old))
                except OSError:
                    pass

        subprocess.run(
            [
                "ffmpeg", "-y", "-i", file_path,
                "-map", "0",
                "-c", "copy",
                "-f", "segment",
                "-segment_time", str(seconds),
                "-reset_timestamps", "1",
                output_pattern,
            ],
            capture_output=True,
            text=True,
            timeout=900,
            check=True,
        )

        parts = sorted(
            os.path.join(os.path.dirname(file_path), name)
            for name in os.listdir(os.path.dirname(file_path))
            if name.startswith(os.path.basename(base) + ".part")
            and os.path.isfile(os.path.join(os.path.dirname(file_path), name))
        )

        if parts and all(os.path.getsize(p) <= TELEGRAM_FILE_LIMIT for p in parts):
            try:
                os.remove(file_path)
            except OSError:
                pass
            return parts

        seconds = max(5, seconds // 2)

    raise RuntimeError("Unable to split file into Telegram-sized parts")


async def send_downloaded_file(chat_id, file_path, is_audio=False, cancel_key=None, source_url=None):
    if cancel_key in cancelled_downloads:
        return False

    extension = os.path.splitext(file_path)[1].lower()
    image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

    caption = source_url if source_url else None

    if extension in image_extensions:
        try:
            await bot.send_photo(chat_id, types.InputFile(file_path), caption=caption)
        except Exception as photo_error:
            logger.warning(
                "send_photo failed; sending image as document: %s",
                photo_error,
                exc_info=True,
            )
            await bot.send_document(chat_id, types.InputFile(file_path), caption=caption)
        return True

    if is_audio:
        await bot.send_audio(chat_id, types.InputFile(file_path), caption=caption)
        return True

    try:
        await bot.send_video(
            chat_id,
            types.InputFile(file_path),
            supports_streaming=True,
            caption=caption,
        )
        return True
    except Exception as video_error:
        logger.warning(
            "send_video failed; sending original file as document: %s",
            video_error,
            exc_info=True,
        )
        await bot.send_document(chat_id, types.InputFile(file_path), caption=caption)
        return True


async def get_media_info(url):
    """Get lightweight metadata for the media preview feature."""
    try:
        import yt_dlp
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "socket_timeout": 10,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, False)
        if not info:
            return None

        duration = info.get("duration")
        if duration:
            minutes, seconds = divmod(int(duration), 60)
            duration_text = f"{minutes}:{seconds:02d}"
        else:
            duration_text = "Unknown"

        return {
            "title": info.get("title") or "Unknown",
            "duration": duration_text,
            "uploader": info.get("uploader") or info.get("channel") or "Unknown",
            "width": info.get("width"),
            "height": info.get("height"),
        }
    except Exception as e:
        logger.debug("Media info unavailable for %s: %s", url, e)
        return None


async def process_download(
    message,
    url,
    is_audio=False,
    is_video_trim=False,
    is_audio_trim=False,
    start_time=None,
    end_time=None,
    quality=None,
):
    download_id = f"{message.chat.id}_{time.time_ns()}"
    progress_message = None
    progress_task = None

    try:
        if not check_memory_usage():
            await send_message(
                message.chat.id,
                "⚠️ Server is currently under high load. Please try again later.",
            )
            return

        active_downloads.add(download_id)
        active_tasks[download_id] = asyncio.current_task()

        async with download_semaphore:
            if is_audio:
                request_type = "Audio Download"
            elif is_video_trim:
                request_type = "Video Trimming"
            elif is_audio_trim:
                request_type = "Audio Trimming"
            else:
                request_type = "Video Download"

            progress_message = await send_message(
                message.chat.id,
                f"📥 Processing {request_type.lower()}...\n"
                f"🆔 Cancel ID: <code>{download_id}</code>",
            )

            async def update_progress():
                started = time.monotonic()
                while True:
                    await asyncio.sleep(PROGRESS_INTERVAL)
                    if not progress_message or download_id in cancelled_downloads:
                        return
                    elapsed = int(time.monotonic() - started)
                    try:
                        await bot.edit_message_text(
                            f"📥 Downloading...\n"
                            f"⏱ Elapsed: {elapsed}s\n"
                            f"🆔 Cancel ID: <code>{download_id}</code>",
                            message.chat.id,
                            progress_message.message_id,
                        )
                    except Exception:
                        return

            progress_task = asyncio.create_task(update_progress())

            platform = detect_platform(url)
            if not platform:
                await send_message(message.chat.id, "⚠️ Unsupported URL.")
                return

            result = None
            last_error = None

            for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
                if download_id in cancelled_downloads:
                    await send_message(message.chat.id, "🛑 Download cancelled.")
                    return

                try:
                    if is_video_trim:
                        result = await run_blocking(
                            process_video_trim, url, start_time, end_time, quality
                        )
                    elif is_audio_trim:
                        result = await run_blocking(
                            process_audio_trim, url, start_time, end_time
                        )
                    elif is_audio:
                        result = await run_blocking(extract_audio_ffmpeg, url)
                    else:
                        if platform == "YouTube":
                            result = await run_blocking(
                                process_youtube, url, quality
                            )
                        else:
                            result = await run_blocking(
                                PLATFORM_HANDLERS[platform], url
                            )

                    if result:
                        break
                    last_error = "No media returned"
                except Exception as e:
                    last_error = str(e)
                    logger.warning(
                        "Download attempt %s/%s failed: %s",
                        attempt, MAX_DOWNLOAD_RETRIES, e,
                        exc_info=True,
                    )

                if attempt < MAX_DOWNLOAD_RETRIES:
                    await send_message(
                        message.chat.id,
                        f"🔄 Download failed. Retrying ({attempt + 1}/{MAX_DOWNLOAD_RETRIES})...",
                    )
                    await asyncio.sleep(2 * attempt)

            if download_id in cancelled_downloads:
                await send_message(message.chat.id, "🛑 Download cancelled.")
                return

            if not result:
                await send_message(
                    message.chat.id,
                    f"❌ Download failed after {MAX_DOWNLOAD_RETRIES} attempts.\n"
                    f"{escape(str(last_error or ''))}",
                )
                return

            if isinstance(result, tuple):
                first = result[0] if result else None
                file_paths = first if isinstance(first, list) else ([first] if first else [])
            else:
                file_paths = [result]

            if not file_paths:
                await send_message(message.chat.id, "❌ Download failed. No media found.")
                return

            for original_path in file_paths:
                if download_id in cancelled_downloads:
                    await send_message(message.chat.id, "🛑 Download cancelled.")
                    return

                if not original_path or not os.path.exists(original_path):
                    logger.warning("File does not exist: %s", original_path)
                    continue

                actual_size = os.path.getsize(original_path)

                if (
                    actual_size > TELEGRAM_FILE_LIMIT
                    and not (is_audio or is_audio_trim)
                ):
                    try:
                        parts = await run_blocking(split_large_file, original_path)
                    except Exception as split_error:
                        logger.error("File split failed: %s", split_error, exc_info=True)
                        await send_message(
                            message.chat.id,
                            f"❌ File is too large and could not be split: {split_error}",
                        )
                        continue
                else:
                    parts = [original_path]

                for part_index, file_path in enumerate(parts, start=1):
                    if download_id in cancelled_downloads:
                        await send_message(message.chat.id, "🛑 Download cancelled.")
                        return

                    try:
                        if len(parts) > 1:
                            await send_message(
                                message.chat.id,
                                f"📦 Sending part {part_index}/{len(parts)}...",
                            )

                        await send_downloaded_file(
                            message.chat.id,
                            file_path,
                            is_audio=is_audio or is_audio_trim,
                            cancel_key=download_id,
                            source_url=url if platform == "Threads" else None,
                        )

                        logger.info("Successfully sent: %s", file_path)
                    except Exception as send_error:
                        logger.error("Error sending file: %s", send_error, exc_info=True)
                        await send_message(
                            message.chat.id,
                            f"❌ Error sending file: {escape(str(send_error))}",
                        )
                    finally:
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                        except Exception as cleanup_error:
                            logger.error("Cleanup error for %s: %s", file_path, cleanup_error)

    except asyncio.CancelledError:
        logger.info("Download task cancelled: %s", download_id)
        raise
    except Exception as e:
        logger.error("Processing error: %s", e, exc_info=True)
        await send_message(message.chat.id, f"❌ An error occurred: {escape(str(e))}")
    finally:
        if progress_task:
            progress_task.cancel()
        active_tasks.pop(download_id, None)
        active_downloads.discard(download_id)
        cancelled_downloads.discard(download_id)
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
                        logger.error("Error cleaning file %s: %s", filepath, e)

            gc.collect()
            await asyncio.sleep(CLEANUP_INTERVAL)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Cleanup task error: %s", e, exc_info=True)
            await asyncio.sleep(60)


async def start_background_tasks():
    logger.info("Starting async background tasks...")
    tasks = [asyncio.create_task(cleanup_files(), name="cleanup")]

    worker_count = min(3, os.cpu_count() or 1)
    logger.info("Starting %s async workers...", worker_count)

    for index in range(worker_count):
        tasks.append(
            asyncio.create_task(worker(), name=f"download-worker-{index + 1}")
        )

    return tasks


@bot.message_handler(commands=["start", "help"], content_types=["text"])
async def send_welcome(message):
    welcome_text = (
        "🤖 Media Download Bot 🤖\n\n"
        "Video/audio downloader with queue, retry, progress and file splitting.\n\n"
        "• YouTube / Shorts\n"
        "• Instagram / Reels / Carousels\n"
        "• Facebook\n"
        "• Twitter/X\n\n"
        "Commands:\n"
        "• Send one or multiple URLs\n"
        "• /audio <URL> - Extract audio\n"
        "• /cancel <ID> - Cancel a running download\n"
        "• /trim <URL> <Start> <End>\n"
        "• /trimAudio <URL> <Start> <End>"
    )
    await bot.send_message(message.chat.id, welcome_text)


@bot.message_handler(commands=["cancel"])
async def handle_cancel(message):
    download_id = message.text.replace("/cancel", "", 1).strip()

    if not download_id:
        await send_message(
            message.chat.id,
            "⚠️ Use: /cancel <Cancel ID>\n"
            "The ID is shown when a download starts.",
        )
        return

    if download_id in active_tasks:
        cancelled_downloads.add(download_id)
        await send_message(
            message.chat.id,
            "🛑 Cancellation requested. The current download will stop "
            "as soon as the active operation returns.",
        )
    else:
        await send_message(message.chat.id, "⚠️ Download ID not found or already finished.")


@bot.message_handler(commands=["video"])
async def handle_video_request(message):
    parts = message.text.split()
    if len(parts) < 2:
        await send_message(message.chat.id, "⚠️ Use: /video <YouTube URL> [quality]\\nQuality: best, 2160p, 1440p, 1080p, 720p, 480p, 360p, 240p, 144p")
        return
    url = next((p for p in parts[1:] if p.startswith(("http://", "https://"))), None)
    quality = next((p.lower() for p in parts[1:] if re.fullmatch(r"(best|\\d{3,4}p)", p.lower())), "best")
    if not url or not re.search(r"(youtube\\.com|youtu\\.be)", url, re.IGNORECASE):
        await send_message(message.chat.id, "⚠️ Please provide a valid YouTube URL.")
        return
    if quality != "best":
        quality = quality[:-1]
    await download_queue.put((message, url, False, False, False, None, None, quality))
    await send_message(message.chat.id, f"🎬 YouTube download added — quality: <b>{escape(quality)}</b>")


@bot.message_handler(commands=["audio"])
async def handle_audio_request(message):
    urls = re.findall(r"https?://[^\s]+", message.text.replace("/audio", "", 1))
    if not urls:
        await send_message(message.chat.id, "⚠️ Please provide a URL.")
        return

    for url in urls:
        await download_queue.put(
            (message, url, True, False, False, None, None, None)
        )

    await send_message(
        message.chat.id,
        f"🎵 Added {len(urls)} audio download(s) to the queue!",
    )


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

    url, start_time, end_time, quality = match.groups()
    quality = quality[:-1] if quality else "best"
    await download_queue.put(
        (message, url, False, True, False, start_time, end_time, quality)
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
        (message, url, False, False, True, start_time, end_time, None)
    )
    await send_message(
        message.chat.id,
        "✂️🎵 Added to audio segment extraction queue!",
    )


@bot.message_handler(
    func=lambda message: not (message.text or "").strip().startswith("/"),
    content_types=["text"],
)
async def handle_message(message):
    urls = re.findall(r"https?://[^\s]+", message.text)

    if not urls:
        await send_message(message.chat.id, "⚠️ Please send a valid media URL.")
        return

    # Feature 14: multiple URLs in one message.
    for url in urls:
        await download_queue.put(
            (message, url, False, False, False, None, None, None)
        )

    if len(urls) == 1:
        # Feature 13: media information preview before download.
        info = await get_media_info(urls[0])
        if info:
            quality = (
                f"{info['width']}x{info['height']}"
                if info.get("width") and info.get("height")
                else "Unknown"
            )
            await send_message(
                message.chat.id,
                f"🎬 <b>{escape(str(info['title']))}</b>\n"
                f"👤 {escape(str(info['uploader']))}\n"
                f"⏱ {info['duration']}\n"
                f"📐 {quality}\n\n"
                f"📥 Added to download queue.",
            )
        else:
            await send_message(
                message.chat.id,
                "🎬 Added to download queue!",
            )
    else:
        await send_message(
            message.chat.id,
            f"🎬 Added {len(urls)} URLs to the download queue!",
        )
