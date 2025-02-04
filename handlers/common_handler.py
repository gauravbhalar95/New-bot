import os
import re
import cloudscraper
from moviepy.editor import VideoFileClip

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Connection": "keep-alive"
}

scraper = cloudscraper.create_scraper()

def process_adult(url):
    domain_handlers = {
        'xvideos.com': download_xvideos,
        'xnxx.com': download_xnxx,
        'xhamster.com': download_xhamster,
        'pornhub.com': download_pornhub,
        'redtube.com': download_redtube,
    }

    for domain, handler in domain_handlers.items():
        if domain in url:
            return handler(url)

    return None, None, None

def extract_video_id(url, site):
    patterns = {
        "xvideos": r"xvideos\.com/video(?:/|\.php\?v=)?(\d+)",
        "xnxx": r"xnxx\.com/video-([a-zA-Z0-9]+)",
        "xhamster": r"xhamster\.com/videos/([a-zA-Z0-9-]+)",
        "pornhub": r"pornhub\.com/view_video\.php\?viewkey=([a-zA-Z0-9]+)",
        "redtube": r"redtube\.com/([0-9]+)"
    }

    match = re.search(patterns.get(site, ""), url)
    return match.group(1) if match else None

def get_video_download_link(video_page_url, regex_patterns):
    response = scraper.get(video_page_url, headers=HEADERS)
    if response.status_code != 200:
        print("❌ Failed to fetch video page.")
        return None

    for pattern in regex_patterns:
        match = re.search(pattern, response.text)
        if match:
            return match.group(1)
    
    print("❌ No valid video link found in page source.")
    return None

def download_video(url, site, regex_patterns):
    try:
        video_id = extract_video_id(url, site)
        if not video_id:
            print("❌ Failed to extract video ID.")
            return None, None, None

        video_url = get_video_download_link(url, regex_patterns)
        if not video_url:
            return None, None, None

        # Define file paths
        temp_path = f"{site}_{video_id}_temp.mp4"
        final_path = f"{site}_{video_id}.mp4"

        # Download the video
        response = scraper.get(video_url, headers=HEADERS, stream=True)
        response.raise_for_status()

        with open(temp_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        print(f"✅ Downloaded temporary file: {temp_path}")

        # Process the video using MoviePy
        try:
            clip = VideoFileClip(temp_path)
            clip.write_videofile(final_path, codec="libx264")
            clip.close()
            os.remove(temp_path)  # Remove temp file after processing
            print(f"✅ Processed and saved: {final_path}")

        except Exception as e:
            print(f"❌ MoviePy processing failed: {e}")
            return None, None, None

        file_size = os.path.getsize(final_path)
        return final_path, file_size, None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None, None

def download_xvideos(url):
    return download_video(url, "xvideos", [
        r'html5player\.setVideoUrlHigh["\'](https?://[^"\']+)["\']',
        r'"videoUrl":"(https?://[^"]+)"'
    ])

def download_xnxx(url):
    return download_video(url, "xnxx", [
        r'html5player\.setVideoUrlHigh["\'](https?://[^"\']+)["\']',
        r'"videoUrl":"(https?://[^"]+)"'
    ])

def download_xhamster(url):
    return download_video(url, "xhamster", [
        r'videoUrl&quot;:&quot;(https://[^&]+)&quot;',
        r'"videoUrl":"(https?://[^"]+)"'
    ])

def download_pornhub(url):
    return download_video(url, "pornhub", [
        r'"videoUrl":"(https?://[^"]+)"',
        r'"quality_720p":"(https?://[^"]+)"'
    ])

def download_redtube(url):
    return download_video(url, "redtube", [
        r'"videoUrl":"(https?://[^"]+)"'
    ])

if __name__ == "__main__":
    test_url = "https://www.xvideos.com/video39694211/russian_girl_fuck_with_indian_hunter"
    file_path, file_size, stream_link = process_adult(test_url)

    if file_path:
        print(f"✅ Video saved at {file_path} (Size: {file_size / (1024 * 1024):.2f} MB)")
    else:
        print("❌ Failed to download video.")