import logging
import gc
import asyncio
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from config import DOWNLOAD_DIR
from utils.instagram_cookies import COOKIES_FILE
from utils.logger import setup_logging


# ================= LOGGER =================
logger = setup_logging(logging.DEBUG)
logger.add("instagram_handler.log", rotation="10 MB", level="DEBUG")


# ================= CONSTANTS =================
SUPPORTED_DOMAINS = ("instagram.com",)
MAX_PARALLEL_DOWNLOADS = 3   # 🔥 change if needed


# ================= URL HELPERS =================
def is_valid_url(url: str) -> bool:
    try:
        r = urlparse(url)
        return r.scheme in ("http", "https") and any(
            d in r.netloc for d in SUPPORTED_DOMAINS
        )
    except Exception:
        return False


def detect_instagram_type(url: str) -> str:
    """
    Auto-detect Instagram content type
    """
    if "/reel/" in url:
        return "reel"
    if "/tv/" in url:
        return "tv"
    if "/p/" in url:
        return "post"
    return "video"


# ================= PROGRESS HOOK =================
def download_progress_hook(d: dict) -> None:
    if d["status"] == "downloading":
        logger.info(
            f"⬇ {d.get('_percent_str', '')} "
            f"{d.get('_speed_str', '')} "
            f"ETA {d.get('_eta_str', '')}"
        )
    elif d["status"] == "finished":
        logger.info(f"✅ Downloaded: {d.get('filename')}")


# ================= AUDIO CHECK =================
def has_audio(video: Path) -> bool:
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "json",
            str(video),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        return '"index"' in r.stdout
    except Exception:
        return False


# ================= YT-DLP OPTIONS =================
def build_ydl_opts(cookie_path: Path) -> dict:
    return {
        # 🧠 SMART HQ FORMAT (NO CRASH)
        "format": "(bv*[ext=mp4]+ba[ext=m4a])/(best[ext=mp4]/best)",

        "merge_output_format": "mp4",

        "outtmpl": str(
            Path(DOWNLOAD_DIR) / "%(uploader)s - %(title)s.%(ext)s"
        ),

        "cookiefile": str(cookie_path),

        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 20,

        "progress_hooks": [download_progress_hook],

        # ❌ NEVER enable generic extractor
        # "force_generic_extractor": True,

        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.instagram.com/",
        },

        "verbose": False,
    }


# ================= SINGLE DOWNLOAD =================
async def download_instagram(url: str) -> tuple[str | None, int, str | None]:
    url = url.split("#")[0]

    cookie_path = Path(COOKIES_FILE)
    if not cookie_path.exists() or cookie_path.stat().st_size == 0:
        return None, 0, "Instagram cookies missing"

    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)

    ydl_opts = build_ydl_opts(cookie_path)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(
                ydl.extract_info, url, True
            )

            if not info:
                return None, 0, "Extraction failed"

            file_path = Path(ydl.prepare_filename(info))

            if not file_path.exists():
                return None, 0, "File not found"

            if not has_audio(file_path):
                return None, 0, "Silent video detected"

            return str(file_path), file_path.stat().st_size, None

    except Exception as e:
        logger.exception("Instagram download failed")
        return None, 0, str(e)


# ================= PARALLEL QUEUE =================
download_queue: asyncio.Queue = asyncio.Queue()


async def instagram_worker(worker_id: int):
    while True:
        url, future = await download_queue.get()
        logger.info(f"[Worker {worker_id}] Processing {url}")

        try:
            result = await download_instagram(url)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
        finally:
            download_queue.task_done()


def start_instagram_workers():
    for i in range(MAX_PARALLEL_DOWNLOADS):
        asyncio.create_task(instagram_worker(i + 1))


async def process_instagram(url: str) -> tuple[str | None, int, str | None]:
    """
    Public API – auto-detect + parallel
    """
    if not is_valid_url(url):
        return None, 0, "Invalid Instagram URL"

    ig_type = detect_instagram_type(url)
    logger.info(f"Detected Instagram type: {ig_type}")

    loop = asyncio.get_running_loop()
    future = loop.create_future()

    await download_queue.put((url, future))
    return await future


# ================= TELEGRAM SEND =================
async def send_video_to_user(bot, chat_id: int, video_path: str):
    try:
        with open(video_path, "rb") as v:
            await bot.send_video(
                chat_id,
                v,
                supports_streaming=True
            )
        logger.info(f"📤 Sent to {chat_id}")
    except Exception as e:
        logger.error(f"Telegram send error: {e}")


# ================= CLEANUP =================
def cleanup_video(path: str):
    try:
        p = Path(path)
        if p.exists():
            p.unlink()
            gc.collect()
    except Exception:
        pass