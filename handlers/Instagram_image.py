import telebot
import os
import re
import requests
import json
from config import API_TOKEN
from utils.renamer import rename_files_in_directory

bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# API Credentials
RAPIDAPI_KEY = "425e3f1022mshd7d4a2d9b3b0136p1fe9b1jsn0bd8321421c7"
RAPIDAPI_HOST = "instagram-downloader-download-instagram-stories-videos4.p.rapidapi.com"

# Ensure 'downloads' directory exists
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def sanitize_filename(filename):
    """
    Sanitize filename to prevent errors.
    - Removes unwanted characters
    - Limits filename length to 100 characters
    """
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    return filename[:100]

def fetch_instagram_media(url):
    """
    Fetch Instagram media URLs using RapidAPI.
    Returns a list of media URLs if available, else an error message.
    """
    url = f"https://{RAPIDAPI_HOST}/convert?url={post_url}"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }

    try:
        response = requests.get(url, headers=headers)
        response_data = response.json()

        if "media" in response_data and response_data["media"]:
            return response_data["media"]  # Return list of media URLs
        return "⚠️ No media found."

    except (json.JSONDecodeError, requests.RequestException) as e:
        return f"❌ Error: {str(e)}"

def get_file_extension(url):
    """Extract file extension from URL"""
    if "." in url.split("/")[-1]:  
        return url.split(".")[-1].split("?")[0]  
    return None  # Return None if no extension found

def download_file(url, file_path):
    """Download file from URL and save it to given path"""
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(file_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024):
                    file.write(chunk)
            return True
        else:
            return False
    except Exception as e:
        print(f"❌ Error downloading file: {e}")
        return False

def process_instagram_post(post_url):
    """Fetch Instagram media, download files, rename them, and send to Telegram."""
    media_urls = fetch_instagram_media(post_url)  # Fetch Instagram media links

    if not isinstance(media_urls, list) or not media_urls:
        bot.send_message(message.chat.id, "❌ Instagram media not found.")
        return

    for i, media_item in enumerate(media_urls, start=1):
        media_url = media_item.get("url")
        media_type = media_item.get("type", "unknown")

        if not media_url:
            bot.send_message(message.chat.id, f"⚠️ No URL found for media item {i}")
            continue

        file_extension = get_file_extension(media_url) or ("mp4" if media_type == "video" else "jpg")
        filename = sanitize_filename(f"{media_type}_{i}.{file_extension}")
        file_path = os.path.join(DOWNLOAD_DIR, filename)

        if not download_file(media_url, file_path):
            bot.send_message(message.chat.id, f"❌ Failed to download {filename}")
            continue

        if not os.path.exists(file_path):
            bot.send_message(message.chat.id, f"⚠️ File not found: {filename}")
            continue  # Skip sending if file is missing

        # 🆕 **Use renamer utility before sending**
        renamed_file_path = rename_files_in_directory(file_path)  
        
        try:
            with open(renamed_file_path, "rb") as file:
                if media_type in ["image", "story"]:
                    bot.send_photo(message.chat.id, file, caption=f"📸 Instagram {media_type.capitalize()}")
                elif media_type == "video":
                    bot.send_video(message.chat.id, file, caption=f"🎥 Instagram {media_type.capitalize()}")

            os.remove(renamed_file_path)  # Delete file after sending

        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error sending {media_type}: {e}")