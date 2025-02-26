import telebot
import os
import re
import requests
import json
from config import API_TOKEN
from utils.renamer import rename_files_in_directory  # Ensure this exists

# Initialize Telegram Bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# API Credentials
RAPIDAPI_KEY = "425e3f1022mshd7d4a2d9b3b0136p1fe9b1jsn0bd8321421c7"
RAPIDAPI_HOST = "instagram-downloader-download-instagram-stories-videos4.p.rapidapi.com"

# Ensure 'downloads' directory exists
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def sanitize_filename(filename):
    """Sanitize filename to remove unwanted characters and limit length."""
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    return filename[:100]

def fetch_instagram_media(url):
    """Fetch Instagram media URLs using RapidAPI."""
    api_url = f"https://{RAPIDAPI_HOST}/convert?url={url}"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }

    try:
        response = requests.get(api_url, headers=headers)
        response_data = response.json()

        if "media" in response_data and response_data["media"]:
            return response_data["media"]  # Return list of media URLs
        return None

    except (json.JSONDecodeError, requests.RequestException) as e:
        return None

def get_file_extension(url):
    """Extract file extension from URL."""
    filename = url.split("/")[-1]
    return filename.split(".")[-1].split("?")[0] if "." in filename else None

def download_file(url, file_path):
    """Download file from URL and save it to given path."""
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(file_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024):
                    file.write(chunk)
            return True
    except Exception as e:
        print(f"❌ Error downloading file: {e}")
    return False

def process_instagram_post(url, chat_id):
    """Fetch Instagram media, download files, rename them, and send to Telegram."""
    media_urls = fetch_instagram_media(url)  # Fetch Instagram media links

    if not media_urls:
        bot.send_message(chat_id, "❌ Instagram media not found.")
        return

    for i, media_item in enumerate(media_urls, start=1):
        media_url = media_item.get("url")
        media_type = media_item.get("type", "unknown")

        if not media_url:
            bot.send_message(chat_id, f"⚠️ No URL found for media item {i}")
            continue

        file_extension = get_file_extension(media_url) or ("mp4" if media_type == "video" else "jpg")
        filename = sanitize_filename(f"{media_type}_{i}.{file_extension}")
        file_path = os.path.join(DOWNLOAD_DIR, filename)

        if not download_file(media_url, file_path):
            bot.send_message(chat_id, f"❌ Failed to download {filename}")
            continue

        if not os.path.exists(file_path):
            bot.send_message(chat_id, f"⚠️ File not found: {filename}")
            continue  # Skip sending if file is missing

        renamed_file_path = rename_files_in_directory(file_path)  # Rename before sending

        try:
            with open(renamed_file_path, "rb") as file:
                if media_type in ["image", "story"]:
                    bot.send_photo(chat_id, file, caption=f"📸 Instagram {media_type.capitalize()}")
                elif media_type == "video":
                    bot.send_video(chat_id, file, caption=f"🎥 Instagram {media_type.capitalize()}")

            os.remove(renamed_file_path)  # Delete file after sending

        except Exception as e:
            bot.send_message(chat_id, f"❌ Error sending {media_type}: {e}")

