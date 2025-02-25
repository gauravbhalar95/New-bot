import os
import re
import requests
import json
from config import RAPIDAPI_KEY, RAPIDAPI_HOST

# Ensure 'downloads' directory exists
if not os.path.exists("downloads"):
    os.makedirs("downloads")

def sanitize_filename(filename):
    """Sanitize and trim filename to prevent errors."""
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename.strip())  # Remove unwanted characters
    return filename[:100] if filename else "default_filename"

def fetch_instagram_media(post_url):
    """Fetch Instagram media URLs using RapidAPI"""
    url = f"https://{RAPIDAPI_HOST}/convert?url={post_url}"
    headers = {
        'x-rapidapi-key': RAPIDAPI_KEY,
        'x-rapidapi-host': RAPIDAPI_HOST
    }
    try:
        response = requests.get(url, headers=headers)
        response_data = response.json()
        if "media" in response_data and response_data["media"]:
            return response_data["media"]  # List of media
    except (json.JSONDecodeError, requests.RequestException):
        pass
    return None

def get_file_extension(media_item):
    """Determine file extension based on media type"""
    media_type = media_item.get("type", "").lower()
    return "jpg" if media_type == "image" else "mp4" if media_type == "video" else "bin"

def download_instagram_media(post_url):
    """Download all media from an Instagram post automatically"""
    media_items = fetch_instagram_media(post_url)
    downloaded_files = []

    if media_items:
        for i, media_item in enumerate(media_items, start=1):
            media_url = media_item.get("url")
            file_extension = get_file_extension(media_item)
            filename = f"Instagram_{i}.{file_extension}"
            sanitized_filename = sanitize_filename(filename)
            filepath = os.path.join("downloads", sanitized_filename)

            try:
                response = requests.get(media_url, stream=True)
                if response.status_code == 200:
                    with open(filepath, "wb") as file:
                        for chunk in response.iter_content(1024):
                            file.write(chunk)
                    downloaded_files.append(filepath)
                    print(f"✅ Downloaded: {filepath}")
                else:
                    print(f"❌ Failed to download: {media_url}")
            except Exception as e:
                print(f"❌ Error downloading {media_url}: {str(e)}")

    return downloaded_files  # Returns list of downloaded file paths

# Example usage:
# post_url = "https://www.instagram.com/p/xyz/"
# download_instagram_media(post_url)