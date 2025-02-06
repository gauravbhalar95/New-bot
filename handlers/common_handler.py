import os
import telebot
import yt_dlp
import cloudscraper
from config import API_TOKEN  # Import API Token

# Initialize bot with API Token
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

# CloudScraper settings (for scraping content if needed)
scraper = cloudscraper.create_scraper()

# Supported adult sites
SUPPORTED_SITES = [
    "xvideos.com", "xnxx.com", "xhamster.com", "pornhub.com",
    "redtube.com", "tube8.com", "spankbang.com"
]

# Maximum file size for download (in bytes)
MAX_DOWNLOAD_SIZE = 100 * 1024 * 1024  # 100MB limit

def process_adult(url):
    """
    Process adult video URL: 
    - If the video is under the size limit, download it.
    - Otherwise, return the streaming URL.
    """
    try:
        # YouTube-DL options for fetching and downloading the video
        ydl_opts = {
            'outtmpl': 'output_path',  # Template for output file path
            'format': 'mp4/best',      # Download the best quality mp4
            'noplaylist': True,        # Ignore playlists (download one video)
            'socket_timeout': 10,      # Timeout for sockets
            'retries': 5,              # Retry 5 times on failure
            'quiet': False,            # Show process output
            'nocheckcertificate': True, # Disable certificate check
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'  # User agent string for scraping
            },
            'verbose': True  # Verbose output for debugging
        }

        # Extract video info (without downloading it)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info.get('url')  # Direct streaming URL
            file_size = info.get('filesize') or 0  # Handle None case
            file_name = info.get('title', 'video.mp4')  # Default to 'video.mp4' if no title
            thumbnail = info.get('thumbnail')  # Get video thumbnail

        # If the file size is under the limit, download it
        if file_size and file_size <= MAX_DOWNLOAD_SIZE:
            ydl_opts['outtmpl'] = file_name  # Set the output file name
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])  # Download the video
            return file_name, file_size, thumbnail, True  # Download successful

        # If the video is too large, return the streaming URL
        return video_url, file_size, thumbnail, False  # Streaming link

    except Exception as e:
        # Print any error that occurs during the process
        print(f"Error processing URL: {url} - {e}")
        return None, None, None, None  # Return None in case of error