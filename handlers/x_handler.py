import os
import asyncio
import yt_dlp
import subprocess
import logging
import snscrape.modules.twitter as sntwitter
import requests
from utils.logger import setup_logging
from config import DOWNLOAD_DIR, X_FILE

# Initialize logger
logger = setup_logging(logging.DEBUG)

async def download_twitter_media(url):
    """
    Downloads a Twitter/X video using yt-dlp.
    Falls back to snscrape if yt-dlp fails.
    """
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bv+ba/b',
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'cookiefile': X_FILE,
        'continuedl': True,
        'http_chunk_size': 1048576,  # 1 MB chunk size
        'quiet': False,
        'nocheckcertificate': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://x.com/'
        }
    }

    try:
        loop = asyncio.get_running_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await loop.run_in_executor(None, ydl.extract_info, url, True)

            if not info_dict or "requested_downloads" not in info_dict:
                logger.error("❌ yt-dlp: No video found.")
                return None, None  

            file_path = info_dict["requested_downloads"][0]["filepath"]
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            logger.info(f"✅ yt-dlp: Download completed: {file_path}")
            return file_path, file_size

    except yt_dlp.DownloadError as e:
        logger.error(f"⚠️ yt-dlp failed with an error: {e}")
        return None, None  

    except Exception as e:
        logger.warning(f"⚠️ yt-dlp crashed unexpectedly: {e}")
        logger.info("🔄 Falling back to snscrape...")

        # Extract direct video URL using snscrape
        try:
            tweet_id = url.split("/")[-1]  
            tweet = next(sntwitter.TwitterTweetScraper(tweet_id).get_items())

            if hasattr(tweet, "media"):
                video_urls = [
                    variant.url for media in tweet.media if isinstance(media, sntwitter.Video)
                    for variant in media.variants
                ]
                if video_urls:
                    best_video_url = sorted(video_urls, key=lambda x: int(x.split("bitrate=")[-1].split("&")[0]) if "bitrate=" in x else 0, reverse=True)[0]
                    
                    # Download manually
                    return await download_file(best_video_url, os.path.join(DOWNLOAD_DIR, f"{tweet_id}.mp4"))

        except Exception as scrape_error:
            logger.error(f"❌ snscrape failed: {scrape_error}")

    return None, None

async def download_file(url, file_path):
    """
    Downloads a file from a URL.
    """
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(file_path, "wb") as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            file_size = os.path.getsize(file_path)
            logger.info(f"✅ Direct download completed: {file_path}")
            return file_path, file_size
        else:
            logger.error(f"❌ Failed to download {url}")
    except Exception as e:
        logger.error(f"❌ Download error: {e}")

    return None, None