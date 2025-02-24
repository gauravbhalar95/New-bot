import os
import requests
import re
from utils.sanitize import sanitize_filename
from utils.logger import log_message

# RapidAPI Key અને API URL
RAPIDAPI_KEY = "425e3f1022mshd7d4a2d9b3b0136p1fe9b1jsn0bd8321421c7"
BASE_URL = "instagram-realtimeapi.p.rapidapi.com"

# Headers for authentication
HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": BASE_URL
}

# Ensure 'downloads' directory exists
if not os.path.exists("downloads"):
    os.makedirs("downloads")

def extract_username_from_url(url):
    """Extract Instagram username from URL"""
    match = re.search(r"instagram\\.com/([^/?]+)", url)
    return match.group(1) if match else None

def get_instagram_content(url):
    """Fetch Instagram Posts and Images"""
    if not url:
        return "❌ Error: URL is not provided!"

    post_url = f"https://{BASE_URL}/instagram/posts/url"
    params = {"url": url}
    response = requests.get(post_url, headers=HEADERS, params=params)

    if response.status_code == 200:
        data = response.json()
        if "posts" in data and data["posts"]:
            image_paths = []
            for i, post in enumerate(data["posts"], start=1):
                filename = sanitize_filename(f"downloads/Post_{i}.jpg")
                with open(filename, "wb") as f:
                    f.write(requests.get(post['url']).content)
                image_paths.append(filename)
            
            return image_paths  # Return list of image file paths
        else:
            return "⚠️ No Instagram Posts found."
    else:
        return f"❌ Failed to fetch Instagram content. Status Code: {response.status_code}"