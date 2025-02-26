# handlers/trim_handlers.py
import os
import logging
from telegram import Update
from telegram.ext import CallbackContext
import yt_dlp

from config import DOWNLOAD_DIR
from utils.logger import setup_logging
from utils.sanitize import sanitize_filename  # Assuming you have sanitize.py

logger = setup_logging(logging.DEBUG)  # Adjust logging level as needed

def download_and_trim_video(youtube_url, start_time, end_time):
    """Download and trim video from YouTube using yt-dlp with postprocessor_args."""
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),  # Save video in DOWNLOAD_DIR
        'postprocessor_args': ['-ss', start_time, '-to', end_time],  # FFmpeg trimming arguments
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',  # Use FFmpeg for post-processing
            'preferedformat': 'mp4',  # Convert to mp4
        }]
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(youtube_url, download=True)
            video_filename = os.path.join(DOWNLOAD_DIR, f"{result['id']}.mp4")
            logger.info(f"Trimmed video downloaded: {video_filename}")
            return video_filename
    except Exception as e:
        logger.error(f"Error downloading and trimming video: {e}")
        return None

def trim_command(update: Update, context: CallbackContext):
    """Handles the /trim command."""
    try:
        if len(context.args) < 3:
            update.message.reply_text("Usage: /trim <youtube_url> <start_time> <end_time>")
            return

        youtube_url, start_time, end_time = context.args[0], context.args[1], context.args[2]

        video_filename = download_and_trim_video(youtube_url, start_time, end_time)

        if video_filename:
            with open(video_filename, 'rb') as video:
                update.message.reply_video(video)
            os.remove(video_filename)  # Clean up after sending
        else:
            update.message.reply_text("Failed to download and trim the video.")

    except Exception as e:
        logger.error(f"Error during trim command: {e}")
        update.message.reply_text("An error occurred while processing your request.")
