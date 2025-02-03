import os
import re
import requests
from utils.sanitize import sanitize_filename

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

def sanitize_filename(filename, max_length=250):
    return file
def extract_video_id(url):
    """Extract the video ID from an Xvideos URL."""
    match = re.search(r"xvideos\.com/video[./]([a-zA-Z0-9]+)", url)
    return match.group(1) if match else None

def get_xvideos_download_link(video_id):
    """Fetch the actual download link for an Xvideos video."""
    video_page_url = f"https://www.xvideos.com/video{video_id}"
    response = requests.get(video_page_url, headers=HEADERS)

    if response.status_code != 200:
        print(f"Error fetching video page: {response.status_code}")
        return None

    # Extract MP4 URL from page source
    match = re.search(r'html5player\.setVideoUrlHigh["\'](https?://[^"\']+)["\'];', response.text)
    return match.group(1) if match else None

def download_xvideos(url):
    """Download video from Xvideos using the extracted video ID."""
    try:
        # Extract video ID
        video_id = extract_video_id(url)
        if not video_id:
            print(f"Error: Could not extract video ID from URL: {url}")
            return None, None, None

        # Get the direct MP4 download link
        download_url = get_xvideos_download_link(video_id)
        if not download_url:
            print("Error: Could not retrieve the video download link.")
            return None, None, None

        # Download video
        response = requests.get(download_url, headers=HEADERS, stream=True)
        response.raise_for_status()

        file_path = f"xvideos_{video_id}.mp4"
        with open(file_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        file_size = os.path.getsize(file_path)
        return file_path, file_size, None

    except Exception as e:
        print(f"Error downloading from Xvideos: {e}")
        return None, None, None

def handle_xvideos(url):
    """Handles video download for Xvideos."""
    if "xvideos.com" in url:
        print(f"Processing Xvideos URL: {url}")
        file_path, file_size, thumb_path = download_xvideos(url)

        if file_path:
            print(f"Download successful! File saved as {file_path}. Size: {file_size / (1024 * 1024):.2f} MB")
            return file_path, file_size, thumb_path
        else:
            print("Download failed.")
            return None, None, None
    else:
        print("Error: Invalid Xvideos URL.")
        return None, None, None

# Example Usage
if __name__ == "__main__":
    test_url = "https://www.xvideos.com/video.otuhkkf6b3f/39694211/0/russian_girl_fuck_with_indian_hunter"
    result = handle_xvideos(test_url)
    if result[0]:
        print(f"Video saved at {result[0]}")
    else:
        print("Failed to download video.")