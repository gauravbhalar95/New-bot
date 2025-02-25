import os
import re
import requests
import json
import mimetypes

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

def fetch_instagram_media(post_url):
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
    """
    Get file extension based on MIME type or extract from URL.
    """
    try:
        response = requests.head(url, allow_redirects=True)
        content_type = response.headers.get("Content-Type")

        if content_type:
            extension = mimetypes.guess_extension(content_type)
            if extension:
                return extension.lstrip('.')  # Remove leading dot
    except requests.RequestException:
        pass  # Ignore errors and fallback to URL-based extraction

    return url.split(".")[-1].split("?")[0]  # Extract from URL

def download_file(file_url, filename):
    """
    Download file from URL and save locally in the 'downloads' directory.
    """
    try:
        response = requests.get(file_url, stream=True)
        if response.status_code == 200:
            filename = sanitize_filename(filename)
            filepath = os.path.join(DOWNLOAD_DIR, filename)

            with open(filepath, "wb") as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)

            print(f"✅ Downloaded: {filename}")
        else:
            print(f"❌ Failed to download: {filename} (Status Code: {response.status_code})")

    except Exception as e:
        print(f"❌ Error downloading {filename}: {str(e)}")

def process_instagram_post(message, post_url):
    """
    Fetch Instagram media, download files, and send to Telegram.
    """
    media_urls = fetch_instagram_media(post_url)

    if isinstance(media_urls, list):
        for i, media_item in enumerate(media_urls, start=1):
            media_url = media_item.get("url")

            if media_url:
                file_extension = get_file_extension(media_url) or "jpg"  # Default to .jpg
                media_type = media_item.get("type", "unknown")  # e.g., image, video, story
                filename = f"{media_type.capitalize()}_{i}.{file_extension}"
                
                download_file(media_url, filename)  # Download file
                
                file_path = os.path.join(DOWNLOAD_DIR, filename)

                # Send to Telegram
                with open(file_path, "rb") as file:
                    if media_type in ["image", "story"]:
                        bot.send_photo(message.chat.id, file, caption=f"📸 Instagram {media_type.capitalize()}")
                    elif media_type == "video":
                        bot.send_video(message.chat.id, file, caption=f"🎥 Instagram {media_type.capitalize()}")

                os.remove(file_path)  # Clean up after sending

            else:
                bot.send_message(message.chat.id, f"⚠️ No URL found in media item {i}")

    else:
        bot.send_message(message.chat.id, media_urls)  # Send error message if media not found