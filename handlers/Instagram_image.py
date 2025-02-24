import os
import requests
import re

# RapidAPI Key અને API URL
RAPIDAPI_KEY = "425e3f1022mshd7d4a2d9b3b0136p1fe9b1jsn0bd8321421c7"
BASE_URL = "instagram-scraper-api2.p.rapidapi.com"

# Headers for authentication
HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": "instagram-scraper-api2.p.rapidapi.com"
}

# Ensure 'downloads' directory exists
if not os.path.exists("downloads"):
    os.makedirs("downloads")

def sanitize_filename(name):
    """ Remove invalid filename characters """
    return re.sub(r'[<>:"/\\|?*]', '_', name)  

def extract_username_from_url(url):
    """Extract Instagram username from URL"""
    match = re.search(r"instagram\.com/([^/?]+)", url)
    return match.group(1) if match else None

def get_instagram_content(url):
    """Fetch Instagram Stories and Images"""
    username = extract_username_from_url(url)

    if not username:
        print("Invalid Instagram URL")
        return

    # Stories API Call
    story_url = f"https://{BASE_URL}/v1/stories"
    story_params = {"username": username}
    story_response = requests.get(story_url, headers=HEADERS, params=story_params)

    # Image API Call
    image_url = f"https://{BASE_URL}/v1/images"
    image_params = {"username": username}
    image_response = requests.get(image_url, headers=HEADERS, params=image_params)

    # Process Stories
    if story_response.status_code == 200:
        story_data = story_response.json()
        if "stories" in story_data and story_data["stories"]:
            print("\nInstagram Stories Found:")
            for story in story_data["stories"]:
                filename = sanitize_filename(f"downloads/Story by {username}.jpg")
                with open(filename, "wb") as f:
                    f.write(requests.get(story['url']).content)
                print(f"Downloaded: {filename}")
        else:
            print("\nNo Instagram Stories found.")

    # Process Images
    if image_response.status_code == 200:
        image_data = image_response.json()
        if "images" in image_data and image_data["images"]:
            print("\nInstagram Images Found:")
            for image in image_data["images"]:
                filename = sanitize_filename(f"downloads/Post by {username}.jpg")
                with open(filename, "wb") as f:
                    f.write(requests.get(image['url']).content)
                print(f"Downloaded: {filename}")
        else:
            print("\nNo Instagram Images found.")

# Test Call
url = "https://www.instagram.com/shital_8811__jain/"
get_instagram_content(url)