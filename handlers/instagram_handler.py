import os
import logging
import yt_dlp
import re
from urllib.parse import urlparse
import gc  # Garbage collection for memory cleanup
import subprocess  # For running ffmpeg
from config import DOWNLOAD_DIR, DOWNLOAD_DIR2, DOWNLOAD_DIR3, INSTAGRAM_FILE, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD
from utils.sanitize import is_valid_url  # Sanitization utility

logger = logging.getLogger(__name__)

SUPPORTED_DOMAINS = ['instagram.com']

def is_valid_url(url):
    try:
        result = urlparse(url)
        return result.scheme in ['http', 'https'] and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
    except ValueError:
        return False

def sanitize_filename(name):
    return re.sub(r'[\/:*?"<>|]', '', name)

def ensure_download_dir_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def download_progress_hook(d):
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '0%')
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        logger.info(f"Downloading... {percent} at {speed}, ETA: {eta}")
    elif d['status'] == 'finished':
        logger.info(f"Download finished: {d['filename']}")

def get_download_directory(url):
    if '/stories/' in url or '/stories' in url:
        ensure_download_dir_exists(DOWNLOAD_DIR3)
        return DOWNLOAD_DIR3
    elif '/p/' in url or '/reel/' in url:
        ensure_download_dir_exists(DOWNLOAD_DIR)
        return DOWNLOAD_DIR
    else:
        ensure_download_dir_exists(DOWNLOAD_DIR2)
        return DOWNLOAD_DIR2

def merge_with_ffmpeg(video_path, audio_path, output_path):
    try:
        command = [
            'ffmpeg', '-y', '-i', video_path, '-i', audio_path,
            '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental', output_path
        ]
        subprocess.run(command, check=True)
        logger.info(f'Merged files into {output_path}')
        return output_path
    except subprocess.CalledProcessError as e:
        logger.error(f'Error merging files with ffmpeg: {e}')
        return None

def process_instagram(url):
    download_directory = get_download_directory(url)

    ydl_opts = {
    'username': INSTAGRAM_USERNAME,
    'password': INSTAGRAM_PASSWORD,
    'format': 'bv+ba/b',
    'outtmpl': f'{download_directory}/{sanitize_filename("%(title)s")}.%(ext)s',
    'cookiefile':INSTAGRAM_FILE,
    'socket_timeout': 10,
    'retries': 5,
    'progress_hooks': [download_progress_hook],
    'logger': logger,
    'verbose': True,
    'noplaylist': True,
}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info_dict)
            
            # Check if there are separate video and audio files
            if 'requested_downloads' in info_dict:
                video_file = None
                audio_file = None
                for f in info_dict['requested_downloads']:
                    if f['ext'] in ['mp4', 'mkv', 'webm']:
                        video_file = f['_filename']
                    elif f['ext'] in ['m4a', 'mp3', 'opus']:
                        audio_file = f['_filename']
                
                if video_file and audio_file:
                    merged_file = os.path.join(download_directory, sanitize_filename(info_dict['title']) + '_merged.mp4')
                    merge_with_ffmpeg(video_file, audio_file, merged_file)
                    return merged_file, info_dict.get('filesize', 0), None
            return filename, info_dict.get('filesize', 0), None
    except Exception as e:
        logger.error(f"Error downloading Instagram content: {e}")
        return None, 0, None

def send_media_to_user(bot, chat_id, media_path, media_type="video"):
    try:
        with open(media_path, 'rb') as media:
            if media_type == "video":
                bot.send_video(chat_id, media)
            elif media_type == "photo":
                bot.send_photo(chat_id, media)
            logger.info(f"{media_type.capitalize()} sent to user {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send {media_type} to user {chat_id}: {e}")

def cleanup_media(media_path):
    try:
        if os.path.exists(media_path):
            os.remove(media_path)
            gc.collect()
            logger.info(f"Cleaned up {media_path}")
    except Exception as e:
        logger.error(f"Failed to clean up {media_path}: {e}")