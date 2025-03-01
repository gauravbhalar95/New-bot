import os
import re
import requests
import yt_dlp

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

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
        return None, None

    # Extract MP4 URL (High Quality)
    mp4_match = re.search(r'html5player\.setVideoUrlHigh["\'](https?://[^"\']+)["\']', response.text)
    if mp4_match:
        return mp4_match.group(1), "mp4"

    # Extract M3U8 Streaming Link (if available)
    m3u8_match = re.search(r'html5player\.setVideoHLS["\'](https?://[^"\']+)["\']', response.text)
    if m3u8_match:
        return m3u8_match.group(1), "m3u8"

    return None, None

def download_xvideos(url):
    """Download video from Xvideos using the extracted video ID."""
    try:
        video_id = extract_video_id(url)
        if not video_id:
            print(f"Error: Could not extract video ID from URL: {url}")
            return None, None, None

        download_url, format_type = get_xvideos_download_link(video_id)
        if not download_url:
            print("Error: Could not retrieve the video download link.")
            return None, None, None

        if format_type == "m3u8":
            print(f"✅ Streaming link found: {download_url}")
            return None, None, download_url  # Return streaming link instead of a file

        # Download MP4 Video
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

def download_using_ytdlp(url):
    """Fallback downloader using yt-dlp."""
    ydl_opts = {
        "format": "best",
        "outtmpl": "xvideos_%(id)s.%(ext)s",
        "retries": 5,
        "socket_timeout": 10,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info_dict = ydl.extract_info(url, download=True)
            file_path = f"xvideos_{info_dict['id']}.{info_dict['ext']}"
            file_size = os.path.getsize(file_path)
            return file_path, file_size, None
        except Exception as e:
            print(f"yt-dlp failed: {e}")
            return None, None, None

def handle_xvideos(url):
    """Handles video download for Xvideos."""
    if "xvideos.com" in url:
        print(f"Processing Xvideos URL: {url}")
        file_path, file_size, streaming_url = download_xvideos(url)

        if file_path:
            print(f"✅ Download successful! File saved as {file_path}. Size: {file_size / (1024 * 1024):.2f} MB")
            return file_path, file_size, None
        elif streaming_url:
            print(f"🎥 Streaming available at: {streaming_url}")
            return None, None, streaming_url
        else:
            print("⚠️ Falling back to yt-dlp...")
            return download_using_ytdlp(url)
    else:
        print("❌ Error: Invalid Xvideos URL.")
        return None, None, None

