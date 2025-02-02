import os
import re
import requests

def extract_video_id(url, site):
    """Extract the video ID from the URL based on the site."""
    if site == "xvideos":
        # Regular expression to extract the video ID from Xvideos URL
        match = re.search(r"xvideos\.com/video(\d+)", url)
        if match:
            return match.group(1)  # Return the video ID
    return None

def download_xvideos(url):
    """Download video from Xvideos using the video ID."""
    try:
        # Extract video ID from URL
        video_id = extract_video_id(url, "xvideos")
        if not video_id:
            print(f"Error: Could not extract video ID from URL: {url}")
            return None, None, None

        # Construct the download URL (this is an example, adjust if needed)
        download_url = f"https://www.xvideos.com/video{video_id}/download"

        # Send request to the download URL
        response = requests.get(download_url, stream=True)
        response.raise_for_status()  # Raise an error if the request fails

        # Save the video file
        file_path = f"xvideos_video_{video_id}.mp4"
        with open(file_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        # Return the file path and its size
        file_size = os.path.getsize(file_path)
        return file_path, file_size, None  # No thumbnail available for now

    except Exception as e:
        print(f"Error downloading from Xvideos: {e}")
        return None, None, None

# Domain Handler Function for Xvideos
def handle_xvideos(url):
    """Handles video download for Xvideos."""
    # Check if the URL is a valid Xvideos URL
    if 'xvideos.com' in url:
        print(f"Processing video from Xvideos: {url}")
        file_path, file_size, thumb_path = download_xvideos(url)
        
        if file_path:
            print(f"Download successful! File saved as {file_path}. File size: {file_size / (1024 * 1024):.2f} MB")
            return file_path, file_size, thumb_path
        else:
            print("Download failed.")
            return None, None, None
    else:
        print(f"Error: The URL is not from Xvideos.")
        return None, None, None

# Example Usage
if __name__ == "__main__":
    test_url = "https://www.xvideos.com/video12345678/sample-video-title"
    result = handle_xvideos(test_url)
    if result[0]:
        print(f"Video saved at {result[0]}")
    else:
        print("Failed to download video.")