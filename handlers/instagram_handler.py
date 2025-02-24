import os
import logging
import yt_dlp
import requests
import re
import gc
from urllib.parse import urlparse
from config import DOWNLOAD_DIR, INSTAGRAM_FILE
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging

# RapidAPI Key અને API URL
RAPIDAPI_KEY = "425e3f1022mshd7d4a2d9b3b0136p1fe9b1jsn0bd8321421c7"
BASE_URL = "instagram-scraper-api2.p.rapidapi.com"
HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": "instagram-scraper-api2.p.rapidapi.com"
}

# Logger initialization
logger = setup_logging(logging.DEBUG)
SUPPORTED_DOMAINS = ['instagram.com']

# Ensure 'downloads' directory exists
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

def is_valid_url(url):
    try:
        result = urlparse(url)
        return result.scheme in ['http', 'https'] and any(domain in result.netloc for domain in SUPPORTED_DOMAINS)
    except ValueError:
        return False

def extract_username_from_url(url):
    match = re.search(r"instagram\.com/([^/?]+)", url)
    return match.group(1) if match else None

def is_instagram_video(url):
    return any(x in url for x in ['/reel/', '/tv/', '/video/'])

def download_progress_hook(d):
    if d['status'] == 'downloading':
        logger.info(f"Downloading... {d.get('_percent_str', '0%')} at {d.get('_speed_str', 'N/A')}, ETA: {d.get('_eta_str', 'N/A')}")
    elif d['status'] == 'finished':
        logger.info(f"Download finished: {d['filename']}")

def process_instagram_video(url):
    ydl_opts = {
        'format': 'bv+ba/b',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'cookiefile': INSTAGRAM_FILE,
        'socket_timeout': 10,
        'retries': 5,
        'progress_hooks': [download_progress_hook],
        'logger': logger,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info_dict), info_dict.get('filesize', 0), None
    except Exception as e:
        logger.error(f"Error downloading Instagram video: {e}")
        return None, 0, None

def get_instagram_content(url):
    username = extract_username_from_url(url)
    if not username:
        logger.error("Invalid Instagram URL")
        return
    
    # Fetch stories
    story_response = requests.get(f"https://{BASE_URL}/v1/stories", headers=HEADERS, params={"username": username})
    if story_response.status_code == 200:
        story_data = story_response.json()
        for story in story_data.get("stories", []):
            filename = os.path.join(DOWNLOAD_DIR, sanitize_filename(f"Story_{username}.jpg"))
            with open(filename, "wb") as f:
                f.write(requests.get(story['url']).content)
            logger.info(f"Downloaded: {filename}")
    
    # Fetch images
    image_response = requests.get(f"https://{BASE_URL}/v1/images", headers=HEADERS, params={"username": username})
    if image_response.status_code == 200:
        image_data = image_response.json()
        for image in image_data.get("images", []):
            filename = os.path.join(DOWNLOAD_DIR, sanitize_filename(f"Post_{username}.jpg"))
            with open(filename, "wb") as f:
                f.write(requests.get(image['url']).content)
            logger.info(f"Downloaded: {filename}")

def handle_instagram_url(url):
    if is_instagram_video(url):
        logger.info("Processing Instagram Video/Reel...")
        return process_instagram_video(url)
    else:
        logger.info("Processing Instagram Post/Story...")
        return get_instagram_content(url)
