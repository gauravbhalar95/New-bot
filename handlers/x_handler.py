import os
import tweepy
import requests
import telebot
import logging
from utils.logger import setup_logging
from utils.thumb_generator import generate_thumbnail
from config import DOWNLOAD_DIR, API_TOKEN, TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET

# Initialize logger
logger = setup_logging(logging.DEBUG)

# Initialize Telegram bot
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# Initialize Twitter API client
auth = tweepy.OAuth1UserHandler(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
twitter_api = tweepy.API(auth)

def get_twitter_video_url(url):
    """
    Extracts the highest-quality video URL from a given tweet.
    """
    try:
        tweet_id = tweet_url.split("/")[-1]
        tweet = twitter_api.get_status(tweet_id, tweet_mode="extended")

        if "extended_entities" in tweet._json and "media" in tweet._json["extended_entities"]:
            for media in tweet._json["extended_entities"]["media"]:
                if media["type"] == "video":
                    variants = media["video_info"]["variants"]
                    highest_quality = max(variants, key=lambda v: v.get("bitrate", 0))
                    return highest_quality["url"]

        logger.error("❌ No video found in tweet.")
    except tweepy.TweepError as e:
        logger.error(f"⚠️ Twitter API error: {e}")
    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")

    return None

def download_twitter_video(url):
    """
    Downloads a Twitter video and returns (file_path, file_size, thumbnail_path).
    """
    try:
        response = requests.get(video_url, stream=True)
        if response.status_code != 200:
            logger.error("⚠️ Failed to download video.")
            return None, None, None

        file_name = os.path.join(DOWNLOAD_DIR, "twitter_video.mp4")
        with open(file_name, "wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                file.write(chunk)

        file_size = os.path.getsize(file_name)
        thumbnail_path = generate_thumbnail(file_name)

        logger.info(f"✅ Download completed: {file_name}")
        return file_name, file_size, thumbnail_path

    except Exception as e:
        logger.error(f"⚠️ Unexpected error during download: {e}")
    
    return None, None, None