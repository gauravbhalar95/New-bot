import os
import gc
import logging
import re
import time
import asyncio
import subprocess
import secrets
from html import escape
from datetime import datetime, timezone

from telebot import types
from telebot.async_telebot import AsyncTeleBot

from config import API_TOKEN, TELEGRAM_FILE_LIMIT
from handlers.youtube_handler import process_youtube, extract_audio_ffmpeg
from handlers.instagram_handler import (\n    process_instagram,\n    download_instagram_stories,\n    download_instagram_dp,\n)
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
SPLIT_TARGET_RATIO = 0.85
MAX_UPLOAD_PART_SIZE = 45 * 1024 * 1024

logger = setup_logging(logging.DEBUG)

bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")

download_queue = asyncio.Queue()
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
active_downloads = set()
active_tasks = {}
cancelled_downloads = set()

# Short-lived inline-button requests.
INLINE_REQUEST_TTL = 600
inline_requests = {}
trim_requests = {}

# Short-lived storage for YouTube quality-picker requests.
# Telegram callback_data is limited to 64 bytes, so never put the full URL
# directly into callback_data.
YOUTUBE_REQUEST_TTL = 600
youtube_quality_requests = {}

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
    """Split a large video into Telegram-safe MP4 parts."""
    file_size = os.path.getsize(file_path)

    if file_size <= MAX_UPLOAD_PART_SIZE:
        return [file_path]

    directory = os.path.dirname(file_path) or "."
    base, ext = os.path.splitext(file_path)
    target_size = int(MAX_UPLOAD_PART_SIZE * 0.80)

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if probe.returncode != 0 or not probe.stdout.strip():
        raise RuntimeError(
            f"ffprobe failed: {probe.stderr.strip()[-1000:] or 'unknown error'}"
        )

    try:
        duration = float(probe.stdout.strip().splitlines()[0])
    except ValueError as exc:
        raise RuntimeError(f"Invalid video duration: {probe.stdout!r}") from exc

    if duration <= 0:
        raise RuntimeError("Video duration is zero or unavailable")

    # First try stream-copy splitting. This is fast and preserves quality.
    seconds = max(3, int(duration * target_size / file_size))

    def cleanup_parts():
        prefix = os.path.basename(base) + ".part"
        for name in os.listdir(directory):
            if name.startswith(prefix):
                try:
                    os.remove(os.path.join(directory, name))
                except OSError:
                    pass

    def collect_parts():
        prefix = os.path.basename(base) + ".part"
        return sorted(
            os.path.join(directory, name)
            for name in os.listdir(directory)
            if name.startswith(prefix)
            and os.path.isfile(os.path.join(directory, name))
        )

    for attempt in range(1, 7):
        cleanup_parts()
        pattern = f"{base}.part%03d.mp4"

        process = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-y", "-i", file_path,
                "-map", "0:v:0", "-map", "0:a?",
                "-c", "copy",
                "-f", "segment",
                "-segment_time", str(seconds),
                "-reset_timestamps", "1",
                "-segment_format", "mp4",
                pattern,
            ],
            capture_output=True,
            text=True,
            timeout=900,
        )

        parts = collect_parts()

        if process.returncode == 0 and parts:
            sizes = [os.path.getsize(p) for p in parts]
            if all(size <= MAX_UPLOAD_PART_SIZE for size in sizes):
                logger.info(
                    "Split %s into %d parts; largest %.2f MB",
                    file_path,
                    len(parts),
                    max(sizes) / 1024 / 1024,
                )
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                return parts

        logger.warning(
            f"Stream-copy split attempt {attempt} failed "
            f"(code={process.returncode}, seconds={seconds}): "
            f"{process.stderr.strip()[-1500:]}"
        )

        cleanup_parts()
        seconds = max(3, seconds // 2)

    # Fallback: re-encode each segment. This handles videos whose keyframes,
    # timestamps, or container layout prevent reliable stream-copy splitting.
    logger.warning(f"Using re-encode fallback for large file: {file_path}")
    seconds = max(3, int(duration * target_size / file_size))

    for attempt in range(1, 7):
        cleanup_parts()
        pattern = f"{base}.part%03d.mp4"

        process = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-y", "-i", file_path,
                "-map", "0:v:0", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                "-c:a", "aac", "-b:a", "128k",
                "-f", "segment",
                "-segment_time", str(seconds),
                "-reset_timestamps", "1",
                "-movflags", "+faststart",
                "-segment_format", "mp4",
                pattern,
            ],
            capture_output=True,
            text=True,
            timeout=1800,
        )

        parts = collect_parts()

        if process.returncode == 0 and parts:
            sizes = [os.path.getsize(p) for p in parts]
            if all(size <= MAX_UPLOAD_PART_SIZE for size in sizes):
                logger.info(
                    "Re-encoded split produced %d parts; largest %.2f MB",
                    len(parts),
                    max(sizes) / 1024 / 1024,
                )
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                return parts

        logger.warning(
            f"Re-encode split attempt {attempt} failed "
            f"(code={process.returncode}, seconds={seconds}): "
            f"{process.stderr.strip()[-1500:]}"
        )
        cleanup_parts()
        seconds = max(3, seconds // 2)

    raise RuntimeError(
        f"Unable to split video below "
        f"{MAX_UPLOAD_PART_SIZE / 1024 / 1024:.0f} MB after all attempts"
    )


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
                    actual_size > MAX_UPLOAD_PART_SIZE
                    and not (is_audio or is_audio_trim)
                ):
                    try:
                        parts = await run_blocking(split_large_file, original_path)
                    except Exception as split_error:
                        logger.error(f"File split failed: {split_error}", exc_info=True)
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




async def _send_instagram_files(message, paths, caption_prefix):
    sent = 0
    for path in paths:
        try:
            await bot.send_photo(
                message.chat.id,
                types.InputFile(path),
                caption=caption_prefix if sent == 0 else None,
            )
            sent += 1
        except Exception as send_error:
            logger.warning("Instagram image send failed for %s: %s", path, send_error)
            try:
                await bot.send_document(
                    message.chat.id,
                    types.InputFile(path),
                    caption=caption_prefix if sent == 0 else None,
                )
                sent += 1
            except Exception:
                logger.exception("Could not send Instagram file: %s", path)
        finally:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
    return sent


@bot.message_handler(commands=["story"])
async def handle_instagram_story(message):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await send_message(
            message.chat.id,
            "⚠️ Use: <code>/story username</code> or <code>/story https://instagram.com/username/</code>",
        )
        return

    target = parts[1].strip()
    status = await send_message(message.chat.id, "📥 Fetching Instagram stories...")
    try:
        paths = await run_blocking(download_instagram_stories, target)
        sent = await _send_instagram_files(
            message,
            paths,
            "📸 Instagram Story",
        )
        if sent:
            await send_message(message.chat.id, f"✅ Sent {sent} story item(s).")
        else:
            await send_message(message.chat.id, "❌ No story media could be sent.")
    except Exception as e:
        logger.error("Instagram story command error: %s", e, exc_info=True)
        await send_message(message.chat.id, f"❌ Story download failed: {escape(str(e))}")
    finally:
        if status:
            try:
                await bot.delete_message(message.chat.id, status.message_id)
            except Exception:
                pass


@bot.message_handler(commands=["dp"])
async def handle_instagram_dp(message):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await send_message(
            message.chat.id,
            "⚠️ Use: <code>/dp username</code> or <code>/dp https://instagram.com/username/</code>",
        )
        return

    target = parts[1].strip()
    status = await send_message(message.chat.id, "🖼️ Fetching HD Instagram profile picture...")
    path = None
    try:
        path = await run_blocking(download_instagram_dp, target)
        await bot.send_photo(
            message.chat.id,
            types.InputFile(path),
            caption="🖼️ Instagram HD profile picture",
        )
    except Exception as e:
        logger.error("Instagram DP command error: %s", e, exc_info=True)
        await send_message(message.chat.id, f"❌ DP download failed: {escape(str(e))}")
    finally:
        if status:
            try:
                await bot.delete_message(message.chat.id, status.message_id)
            except Exception:
                pass
        if path:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass


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


def cleanup_inline_requests():
    cutoff = time.time() - INLINE_REQUEST_TTL
    for store in (inline_requests, trim_requests):
        for token in [k for k, v in store.items() if v.get("created_at", 0) < cutoff]:
            store.pop(token, None)


def build_media_action_keyboard(url, chat_id, user_id):
    cleanup_inline_requests()
    token = secrets.token_urlsafe(8).replace("-", "").replace("_", "")
    inline_requests[token] = {"url": url, "chat_id": chat_id, "user_id": user_id, "created_at": time.time()}
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("🎥 Video", callback_data=f"act:video:{token}"), types.InlineKeyboardButton("🎵 Audio", callback_data=f"act:audio:{token}"))
    markup.add(types.InlineKeyboardButton("✂️ Trim Video", callback_data=f"act:trimv:{token}"), types.InlineKeyboardButton("✂️ Trim Audio", callback_data=f"act:trima:{token}"))
    return markup


@bot.callback_query_handler(func=lambda call: call.data.startswith("act:"))
async def handle_media_action_callback(call):
    try:
        _, action, token = call.data.split(":", 2)
        request = inline_requests.pop(token, None)
        if not request or request["chat_id"] != call.message.chat.id or request["user_id"] != call.from_user.id:
            await bot.answer_callback_query(call.id, "This menu expired or belongs to another user.", show_alert=True)
            return
        url = request["url"]
        if action in ("trimv", "trima"):
            trim_token = secrets.token_urlsafe(8).replace("-", "").replace("_", "")
            trim_requests[trim_token] = {"url": url, "chat_id": call.message.chat.id, "user_id": call.from_user.id, "is_video_trim": action == "trimv", "created_at": time.time()}
            kind = "Video" if action == "trimv" else "Audio"
            await bot.answer_callback_query(call.id, f"{kind} trim selected")
            await bot.edit_message_text(f"✂️ <b>{kind} trimming</b>\n\nSend start and end time in one message:\n<code>00:30 01:45</code>\n\nOr:\n<code>00:00:30 00:01:45</code>", call.message.chat.id, call.message.message_id)
            return
        await bot.answer_callback_query(call.id, "Selected")
        if action == "audio":
            await bot.edit_message_text("🎵 Added to audio queue.", call.message.chat.id, call.message.message_id)
            await download_queue.put((call.message, url, True, False, False, None, None, None))
        elif detect_platform(url) == "YouTube":
            await bot.edit_message_text("🎬 <b>Choose YouTube video quality:</b>", call.message.chat.id, call.message.message_id, reply_markup=build_youtube_quality_keyboard(url, call.message.chat.id, call.from_user.id))
        else:
            await bot.edit_message_text("🎥 Added to video queue.", call.message.chat.id, call.message.message_id)
            await download_queue.put((call.message, url, False, False, False, None, None, None))
    except Exception as e:
        logger.error("Media action callback error: %s", e, exc_info=True)
        await bot.answer_callback_query(call.id, "Could not process selection.", show_alert=True)


@bot.message_handler(func=lambda message: any(r["chat_id"] == message.chat.id and r["user_id"] == message.from_user.id for r in trim_requests.values()), content_types=["text"])
async def handle_trim_time_input(message):
    cleanup_inline_requests()
    matches = [(token, r) for token, r in trim_requests.items() if r["chat_id"] == message.chat.id and r["user_id"] == message.from_user.id]
    if not matches:
        return
    token, request = matches[-1]
    match = re.fullmatch(r"\s*(\d{1,2}(?::\d{1,2}){0,2})\s+(\d{1,2}(?::\d{1,2}){0,2})\s*", message.text or "")
    if not match:
        await send_message(message.chat.id, "⚠️ Invalid time format. Send <code>00:30 01:45</code>.")
        return
    start_time, end_time = match.groups()
    to_seconds = lambda value: sum(int(part) * (60 ** i) for i, part in enumerate(reversed(value.split(":"))))
    if to_seconds(start_time) >= to_seconds(end_time):
        await send_message(message.chat.id, "⚠️ End time must be greater than start time.")
        return
    trim_requests.pop(token, None)
    await download_queue.put((message, request["url"], False, request["is_video_trim"], not request["is_video_trim"], start_time, end_time, None))
    await send_message(message.chat.id, "✂️ Added to the trimming queue. Processing will start shortly.")


def cleanup_youtube_quality_requests():
    cutoff = time.time() - YOUTUBE_REQUEST_TTL
    expired = [
        token
        for token, request in youtube_quality_requests.items()
        if request.get("created_at", 0) < cutoff
    ]
    for token in expired:
        youtube_quality_requests.pop(token, None)


def build_youtube_quality_keyboard(url, chat_id, user_id):
    cleanup_youtube_quality_requests()

    token = secrets.token_urlsafe(8).replace("-", "").replace("_", "")
    youtube_quality_requests[token] = {
        "url": url,
        "chat_id": chat_id,
        "user_id": user_id,
        "created_at": time.time(),
    }

    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        ("⚡ Best", "best"),
        ("2160p", "2160"),
        ("1440p", "1440"),
        ("1080p", "1080"),
        ("720p", "720"),
        ("480p", "480"),
        ("360p", "360"),
        ("240p", "240"),
        ("144p", "144"),
    ]

    for label, quality in buttons:
        markup.add(
            types.InlineKeyboardButton(
                label,
                callback_data=f"ytq:{quality}:{token}",
            )
        )

    return markup


@bot.callback_query_handler(func=lambda call: call.data.startswith("ytq:"))
async def handle_youtube_quality_callback(call):
    try:
        parts = call.data.split(":", 2)
        if len(parts) != 3:
            await bot.answer_callback_query(call.id, "Invalid selection.")
            return

        _, quality, token = parts
        valid_qualities = {
            "best", "2160", "1440", "1080", "720",
            "480", "360", "240", "144",
        }

        if quality not in valid_qualities:
            await bot.answer_callback_query(call.id, "Invalid quality.")
            return

        request = youtube_quality_requests.get(token)
        if not request:
            await bot.answer_callback_query(
                call.id,
                "This quality menu expired. Send the YouTube URL again.",
                show_alert=True,
            )
            return

        if request["chat_id"] != call.message.chat.id:
            await bot.answer_callback_query(call.id, "Invalid chat.")
            return

        if request["user_id"] != call.from_user.id:
            await bot.answer_callback_query(
                call.id,
                "This quality menu belongs to another user.",
                show_alert=True,
            )
            return

        url = request["url"]
        youtube_quality_requests.pop(token, None)

        selected = quality if quality == "best" else f"{quality}p"
        await bot.answer_callback_query(call.id, f"Selected {selected}")

        await bot.edit_message_text(
            f"🎬 <b>YouTube</b>\n"
            f"Quality selected: <b>{escape(selected)}</b>\n\n"
            f"📥 Added to download queue.",
            call.message.chat.id,
            call.message.message_id,
        )

        await download_queue.put(
            (call.message, url, False, False, False, None, None, quality)
        )

    except Exception as e:
        logger.error("YouTube quality callback error: %s", e, exc_info=True)
        try:
            await bot.answer_callback_query(
                call.id,
                "Could not start download.",
                show_alert=True,
            )
        except Exception:
            pass


@bot.message_handler(commands=["video"])
async def handle_video_request(message):
    parts = message.text.split()
    url = next(
        (p for p in parts[1:] if p.startswith(("http://", "https://"))),
        None,
    )

    if not url or not re.search(r"(youtube\.com|youtu\.be)", url, re.IGNORECASE):
        await send_message(message.chat.id, "⚠️ Please provide a valid YouTube URL.")
        return

    await bot.send_message(
        message.chat.id,
        "🎬 <b>Choose YouTube video quality:</b>\n\n"
        "Select the quality you want to download.",
        reply_markup=build_youtube_quality_keyboard(
            url,
            message.chat.id,
            message.from_user.id,
        ),
    )


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


TRIM_TIME_PATTERN = r"(?:\d{1,2}:)?(?:\d{1,2}:)?\d{1,2}(?::\d{2})?"


@bot.message_handler(commands=["trim"])
async def handle_video_trim_request(message):
    try:
        match = re.search(
            rf"(https?://[^\\s]+)\\s+({TRIM_TIME_PATTERN})\\s+({TRIM_TIME_PATTERN})",
            message.text or "",
            re.IGNORECASE,
        )

        if not match:
            await send_message(
                message.chat.id,
                "⚠️ Invalid format.\nUse: /trim <URL> <Start> <End>\nExamples: /trim <URL> 00:30 01:45 or /trim <URL> 00:00:30 00:01:45",
            )
            return

        url, start_time, end_time = match.groups()
        await download_queue.put(
            (message, url, False, True, False, start_time, end_time, None)
        )
        await send_message(message.chat.id, "✂️🎬 Added to video trimming queue!")
    except Exception as e:
        logger.error("Video trim command error: %s", e, exc_info=True)
        await send_message(message.chat.id, f"❌ Trim command error: {escape(str(e))}")


@bot.message_handler(commands=["trimAudio"])
async def handle_audio_trim_request(message):
    try:
        match = re.search(
            rf"(https?://[^\\s]+)\\s+({TRIM_TIME_PATTERN})\\s+({TRIM_TIME_PATTERN})",
            message.text or "",
            re.IGNORECASE,
        )

        if not match:
            await send_message(
                message.chat.id,
                "⚠️ Invalid format.\nUse: /trimAudio <URL> <Start> <End>\nExample: /trimAudio <URL> 00:30 01:45",
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
    except Exception as e:
        logger.error("Audio trim command error: %s", e, exc_info=True)
        await send_message(message.chat.id, f"❌ Trim audio command error: {escape(str(e))}")


@bot.message_handler(
    func=lambda message: not (message.text or "").strip().startswith("/"),
    content_types=["text"],
)
async def handle_message(message):
    urls = re.findall(r"https?://[^\s]+", message.text)

    if not urls:
        await send_message(message.chat.id, "⚠️ Please send a valid media URL.")
        return

    # Show inline actions for every supported single URL.
    if len(urls) == 1 and detect_platform(urls[0]):
        url = urls[0]
        await bot.send_message(message.chat.id, "🎬 <b>What do you want to do?</b>", reply_markup=build_media_action_keyboard(url, message.chat.id, message.from_user.id))
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
