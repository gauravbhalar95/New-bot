import os
import re
import requests
from instagram_handlers.py import process_instagram

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

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
        "xvideos": r"xvideos\.com/video[./]([a-zA-Z0-9]+)",
        "xnxx": r"xnxx\.com/video-([a-zA-Z0-9]+)",
        "xhamster": r"xhamster\.com/videos/([a-zA-Z0-9-]+)",
        "pornhub": r"pornhub\.com/view_video\.php\?viewkey=([a-zA-Z0-9]+)",
        "redtube": r"redtube\.com/([0-9]+)"
    }
    
    match = re.search(patterns.get(site, ""), url)
    return match.group(1) if match else None

def get_video_download_link(video_page_url, regex_pattern):
    response = requests.get(video_page_url, headers=HEADERS)
    if response.status_code != 200:
        return None

    match = re.search(regex_pattern, response.text)
    return match.group(1) if match else None

def download_video(url, site, regex_pattern):
    try:
        video_id = extract_video_id(url, site)
        if not video_id:
            return None, None, None

        video_page_url = url
        download_url = get_video_download_link(video_page_url, regex_pattern)

        if not download_url:
            return None, None, None

        response = requests.get(download_url, headers=HEADERS, stream=True)
        response.raise_for_status()

        file_path = f"{site}_{video_id}.mp4"
        with open(file_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        file_size = os.path.getsize(file_path)
        return file_path, file_size, None

    except Exception:
        return None, None, None

def download_xvideos(url):
    return download_video(url, "xvideos", r'html5player\.setVideoUrlHigh["\'](https?://[^"\']+)["\'];')

def download_xnxx(url):
    return download_video(url, "xnxx", r'html5player\.setVideoUrlHigh["\'](https?://[^"\']+)["\'];')

def download_xhamster(url):
    return download_video(url, "xhamster", r'videoUrl&quot;:&quot;(https://[^&]+)&quot;')

def download_pornhub(url):
    return download_video(url, "pornhub", r'"videoUrl":"(https?://[^"]+)"')

def download_redtube(url):
    return download_video(url, "redtube", r'"videoUrl":"(https?://[^"]+)"')

if __name__ == "__main__":
    test_url = "https://www.xvideos.com/video.otuhkkf6b3f/39694211/0/russian_girl_fuck_with_indian_hunter"
    result = process_adult(test_url)

    if result[0]:
        print(f"Video saved at {result[0]}")
    else:
        print("Failed to download video.")