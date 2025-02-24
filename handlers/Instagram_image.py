import os
import requests
import re
import logging
from utils.sanitize import sanitize_filename
from utils.logger import setup_logging

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

def sanitize_filename(name):
    """ Remove invalid filename characters """
    return re.sub(r'[<>:"/\\|?*]', '_', name)  

def extract_username_from_url(url):
    """Extract Instagram username from URL"""
    match = re.search(r"instagram\\.com/([^/?]+)", url)
    return match.group(1) if match else None

def get_instagram_content(url):
    """Fetch Instagram Posts and Images"""
    post_url = f"https://{BASE_URL}/instagram/posts/url"
    params = {"url": url}
    response = requests.get(post_url, headers=HEADERS, params=params)

    if response.status_code == 200:
        data = response.json()
        if "posts" in data and data["posts"]:
            print("\nInstagram Posts Found:")
            for post in data["posts"]:
                filename = sanitize_filename(f"downloads/Post by {extract_username_from_url(url)}.jpg")
                with open(filename, "wb") as f:
                    f.write(requests.get(post['url']).content)
                print(f"Downloaded: {filename}")
        else:
            print("\nNo Instagram Posts found.")
    else:
        print("Failed to fetch Instagram content.")
    
    # Return the response object for use outside the function
    return response

# Get the response from the function
response = get_instagram_content(url)
