import os  
import gc  
import logging  
import threading  
import telebot  
import requests  
import yt_dlp  # Added for streaming link  
from config import API_TOKEN, COOKIES_FILE  
from handlers.youtube_handler import process_youtube
from handlers.Instagram_image import extract_username_from_url
from handlers.instagram_handler import process_instagram  
from handlers.common_handler import process_adult  
from handlers.x_handler import download_twitter_media  
from utils.sanitize import sanitize_filename  
from utils.logger import setup_logging  
from handlers.facebook_handlers import process_facebook  
from queue import Queue  
import psutil  # To monitor memory usage  
import time  
import requests  
from requests.exceptions import ConnectionError  



logger = setup_logging(logging.DEBUG) #Example of setting to debug level.


 
API_VIDEO_KEY = "pbppSfejR10BOokTVRkTyEdPO9mAGsheJNF8dtbVtqt"  
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')  
logger = setup_logging()  
queue = Queue()  
  
SUPPORTED_DOMAINS = {  
    "youtube": (["youtube.com", "youtu.be"], process_youtube),  
    "instagram": (["instagram.com"], process_instagram, extract_username_from_url),  
    "facebook": (["facebook.com"], process_facebook),  
    "twitter": (["x.com", "twitter.com"], download_twitter_media),  
    "adult": (["pornhub.com", "xvideos.com", "redtube.com", "xhamster.com", "xnxx.com"], process_adult),  
}  
  
def detect_platform(url):
    for platform, values in SUPPORTED_DOMAINS.items():
        domains = values[0]
        handlers = values[1:]  

        if any(domain in url for domain in domains):
            if platform == "instagram":
                if "/stories/" in url:
                    return platform, (extract_username_from_url,)
                else:
                    return platform, (process_instagram,)

            return platform, handlers  

    return None, None
  
# Added this function for streaming link using yt-dlp  
def get_streaming_url(url):  
    """  
    Fetches a streaming URL without downloading the video.  
    """  
    ydl_opts = {  
        'format': 'best',  
        'noplaylist': True,  
        'cookiefile': COOKIES_FILE,  # Include cookies  
        'headers': {  
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',  
            'Referer': 'https://x.com/'  
        }  
    }  
    try:  
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  
            info_dict = ydl.extract_info(url, download=False)  
            return info_dict.get('url')  
    except Exception as e:  
        logger.error(f"Error fetching streaming URL: {e}")  
        return None  
  
def upload_to_api_video(file_path):  
    url = "https://ws.api.video/videos"  
    headers = {  
        "Authorization": f"Bearer {API_VIDEO_KEY}"  
    }  
    files = {  
        'file': open(file_path, 'rb')  
    }  
    data = {  
        'title': os.path.basename(file_path)  
    }  
    response = requests.post(url, headers=headers, files=files, data=data)  
    if response.status_code == 201:  
        return response.json()['assets']['player']  
    else:  
        raise Exception("Failed to upload video to api.video")  
  
  
def send_request_with_retries(url, payload, retries=5, delay=3):  
    for attempt in range(retries):  
        try:  
            response = requests.post(url, data=payload)  
            if response.status_code == 200:  
                return response  
            else:  
                logger.error(f"Received unexpected status code {response.status_code}")  
        except ConnectionError as e:  
            logger.error(f"Connection error: {e}")  
            if attempt < retries - 1:  
                logger.info(f"Retrying in {delay} seconds...")  
                time.sleep(delay)  
            else:  
                logger.error("Max retries reached. Request failed.")  
    return None  
  
def download_video(url):  
    platform, handlers = detect_platform(url)  
    if not platform:  
        raise ValueError("Unsupported platform")  

    # Extract the first handler function and call it
    main_handler = handlers[0]  # Get the first function from the tuple
    return main_handler(url)
  
def log_memory_usage():  
    memory = psutil.virtual_memory()  
    logger.info(f"Memory Usage: {memory.percent}% - Free: {memory.available / (1024 * 1024)} MB")  
  
@bot.message_handler(commands=['start'])  
def start(message):  
    bot.reply_to(message, "Welcome! Send me a video link to download or stream.")  
  
def download_and_send_video(message, url):  
    try:  
        if not sanitize_filename(url):  
            bot.reply_to(message, "Invalid or unsupported URL.")  
            return  
        bot.reply_to(message, "Downloading video, please wait...")  
  
        log_memory_usage()  
  
        file_path, file_size, thumbnail_path = download_video(url)  
        if not file_path:  
            bot.reply_to(message, "Error: Video download failed.")  
            return  
  
        log_memory_usage()  
  
        if thumbnail_path and os.path.exists(thumbnail_path):  
            with open(thumbnail_path, 'rb') as thumb:  
                bot.send_photo(message.chat.id, thumb, caption="✅ Here's the thumbnail!")  
  
        if file_size > 50 * 1024 * 1024:  # 50MB limit for Telegram  
            streaming_link = get_streaming_url(url)  # Used yt-dlp for streaming link  
            if streaming_link:  
                bot.reply_to(message, f"Video too large for Telegram. Stream here:\n{streaming_link}")  
            else:  
                bot.reply_to(message, "Failed to get streaming link.")  
        else:  
            with open(file_path, 'rb') as video:  
                bot.send_video(message.chat.id, video)  
  
        if os.path.exists(file_path):  
            os.remove(file_path)  
        if thumbnail_path and os.path.exists(thumbnail_path):  
            os.remove(thumbnail_path)  
  
        log_memory_usage()  
        gc.collect()  
  
    except Exception as e:  
        logger.error(f"Error: {e}")  
        bot.reply_to(message, f"Error occurred: {e}")  
  
def worker():  
    while True:  
        message, url = queue.get()  
        if message == "STOP":  
            break  
        download_and_send_video(message, url)  
        queue.task_done()  
  
@bot.message_handler(func=lambda message: True, content_types=['text'])  
def handle_message(message):  
    queue.put((message, message.text.strip()))  
  
threading.Thread(target=worker, daemon=True).start()