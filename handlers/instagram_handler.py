import os import logging import yt_dlp import re from urllib.parse import urlparse import gc  # Garbage collection for memory cleanup from config import DOWNLOAD_DIR, INSTAGRAM_FILE

def sanitize_filename(filename, max_length=100): """ Removes special characters from the filename and trims it to a maximum length.

Args:
    filename (str): The original filename.
    max_length (int): Maximum allowed length for the filename.

Returns:
    str: The sanitized filename.
"""
# Replace invalid characters with an underscore
filename = re.sub(r'[\\/*?:"<>|]', '_', filename)

# Remove leading and trailing whitespace
filename = filename.strip()

# Trim the filename to the max_length while preserving the extension
base, ext = os.path.splitext(filename)
if len(base) > max_length - len(ext):
    base = base[:max_length - len(ext)]
filename = base + ext

return filename

logger = logging.getLogger(name)

Supported domains

SUPPORTED_DOMAINS = ['instagram.com']

Validate URLs

def is_valid_url(url): try: result = urlparse(url) return result.scheme in ['http', 'https'] and any(domain in result.netloc for domain in SUPPORTED_DOMAINS) except ValueError: return False

Progress hook for downloads

def download_progress_hook(d): if d['status'] == 'downloading': percent = d.get('_percent_str', '0%') speed = d.get('_speed_str', 'N/A') eta = d.get('_eta_str', 'N/A') logger.info(f"Downloading... {percent} at {speed}, ETA: {eta}") elif d['status'] == 'finished': sanitized_filename = sanitize_filename(d['filename']) logger.info(f"Download finished: {sanitized_filename}")

def process_instagram(url): ydl_opts = { 'format': 'best[ext=mp4]/best', 'outtmpl': lambda info_dict: os.path.join(DOWNLOAD_DIR, f"{sanitize_filename(info_dict['title'])}.%(ext)s"), 'cookiefile': INSTAGRAM_FILE if os.path.exists(INSTAGRAM_FILE) else None, 'socket_timeout': 10, 'retries': 5, 'progress_hooks': [download_progress_hook], 'logger': logger, 'verbose': True, } try: with yt_dlp.YoutubeDL(ydl_opts) as ydl: info_dict = ydl.extract_info(url, download=True) filename = sanitize_filename(ydl.prepare_filename(info_dict)) return filename, info_dict.get('filesize', 0), None except Exception as e: logger.error(f"Error downloading Instagram video: {e}") return None, 0, None

Send video to user (bot instance will be passed from main)

def send_video_to_user(bot, chat_id, video_path): try: sanitized_path = sanitize_filename(video_path) with open(sanitized_path, 'rb') as video: bot.send_video(chat_id, video) logger.info(f"Video sent to user {chat_id}") except Exception as e: logger.error(f"Failed to send video to user {chat_id}: {e}")

Cleanup after download

def cleanup_video(video_path): try: sanitized_path = sanitize_filename(video_path) if os.path.exists(sanitized_path): os.remove(sanitized_path) gc.collect() logger.info(f"Cleaned up {sanitized_path}") except Exception as e: logger.error(f"Failed to clean up {sanitized_path}: {e}")

