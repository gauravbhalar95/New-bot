import telebot
import os
import re
import requests
import json
import mimetypes
from urllib.parse import unquote
from config import API_TOKEN

bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# ✅ NEW RapidAPI Credentials
RAPIDAPI_KEY = "425e3f1022mshd7d4a2d9b3b0136p1fe9b1jsn0bd8321421c7"
RAPIDAPI_HOST = "instagram-downloader-download-instagram-videos-stories.p.rapidapi.com"

# 📂 Ensure 'downloads' directory exists
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def sanitize_filename(filename):
    """Sanitize filename to prevent errors."""
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    return filename[:100]

def fetch_instagram_media(post_url):
    """Fetch Instagram media URLs using RapidAPI."""
    url = f"https://{RAPIDAPI_HOST}/index"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }
    payload = {"url": post_url}

    try:
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json()

        if "media" in response_data and response_data["media"]:
            return response_data["media"]
        return "⚠️ No media found."

    except (json.JSONDecodeError, requests.RequestException) as e:
        return f"❌ Error: {str(e)}"

def get_file_extension(url):
    """Extract file extension from URL."""
    if "." in url.split("/")[-1]:  
        return url.split(".")[-1].split("?")[0]  
    return None

def download_file(url, file_path):
    """Download file from URL and save it to given path."""
    try:
        decoded_url = unquote(url)  # ✅ Fix URL Encoding
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.instagram.com/",
        }
        response = requests.get(decoded_url, headers=headers, stream=True)

        if response.status_code == 200:
            with open(file_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024):
                    file.write(chunk)
            return True
        else:
            print(f"❌ Download Failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error downloading file: {e}")
        return False

def process_instagram_post(message, post_url):
    """Fetch Instagram media, download files, and send to Telegram."""
    media_urls = fetch_instagram_media(post_url)

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
        filename = f"{media_type}_{i}.{file_extension}"
        file_path = os.path.join(DOWNLOAD_DIR, filename)

        if not download_file(media_url, file_path):
            bot.send_message(message.chat.id, f"❌ Failed to download {filename}")
            continue

        if not os.path.exists(file_path):
            bot.send_message(message.chat.id, f"⚠️ File not found: {filename}")
            continue

        try:
            with open(file_path, "rb") as file:
                if media_type in ["image", "story"]:
                    bot.send_photo(message.chat.id, file, caption=f"📸 Instagram {media_type.capitalize()}")
                elif media_type == "video":
                    bot.send_video(message.chat.id, file, caption=f"🎥 Instagram {media_type.capitalize()}")

            os.remove(file_path)  # 🗑️ Delete file after sending

        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error sending {media_type}: {e}")

