import os
import logging
from download.yt_dlp_download import download_video
from download.instagram_download import download_instagram_media
from utils.sanitize import sanitize_filename
from config import SUPPORTED_DOMAINS

# Logger
logger = logging.getLogger(__name__)

def download_media(url):
    """
    Determines the platform and downloads media accordingly.

    :param url: The media URL (YouTube, Instagram, etc.).
    :return: File path and file size if successful, else (None, 0).
    """
    if "instagram.com" in url or "instagr.am" in url:
        return download_instagram_media(url)
    elif any(domain in url for domain in SUPPORTED_DOMAINS):
        return download_video(url)
    else:
        logger.error(f"Unsupported URL: {url}")
        return None, 0