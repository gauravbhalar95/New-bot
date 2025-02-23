import requests
import re

# RapidAPI Key અને API URL
RAPIDAPI_KEY = "425e3f1022mshd7d4a2d9b3b0136p1fe9b1jsn0bd8321421c7"
BASE_URL = "instagram-scraper-api2.p.rapidapi.com"

# Headers for authentication
HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": "instagram-scraper-api2.p.rapidapi.com"  # ✅ URL થી 'https://' કાઢ્યું
}

def extract_username_from_url(url):
    """Instagram URL માંથી username કાઢે છે"""
    match = re.search(r"instagram\.com/([^/?]+)", url)
    return match.group(1) if match else None

def get_instagram_content(url):
    """Auto Detect Instagram URL અને ડાઉનલોડ માટે યોગ્ય API કૉલ કરે છે"""
    username = extract_username_from_url(url)

    if not username:
        print("Invalid Instagram URL")
        return

    # Stories API Call
    story_url = f"https://{BASE_URL}/v1/stories"  # ✅ 'https://' ઉમેર્યું
    story_params = {"username": username}
    story_response = requests.get(story_url, headers=HEADERS, params=story_params)

    # Image API Call
    image_url = f"https://{BASE_URL}/v1/images"  # ✅ 'https://' ઉમેર્યું
    image_params = {"username": username}
    image_response = requests.get(image_url, headers=HEADERS, params=image_params)

    # Process Stories
    if story_response.status_code == 200:
        story_data = story_response.json()
        if "stories" in story_data and story_data["stories"]:
            print("\nInstagram Stories Found:")
            for story in story_data["stories"]:
                print(f"Story URL: {story['url']}")
        else:
            print("\nNo Instagram Stories found.")
    else:
        print(f"Error Fetching Stories: {story_response.status_code}, {story_response.text}")

    # Process Images
    if image_response.status_code == 200:
        image_data = image_response.json()
        if "images" in image_data and image_data["images"]:
            print("\nInstagram Images Found:")
            for image in image_data["images"]:
                print(f"Image URL: {image['url']}")
        else:
            print("\nNo Instagram Images found.")
    else:
        print(f"Error Fetching Images: {image_response.status_code}, {image_response.text}")

