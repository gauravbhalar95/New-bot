import os
import yt_dlp
import logging
import requests
import ffmpeg
from pytube import YouTube
from utils.sanitize import sanitize_filename
from utils.thumb_generator import generate_thumbnail
from config import DOWNLOAD_DIR, COOKIES_FILE

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_youtube(url):
    """
    Downloads a YouTube video using yt-dlp. Falls back to pytube if yt-dlp fails.
    """
    output_path = os.path.join(DOWNLOAD_DIR, sanitize_filename(f"{url.split('v=')[1]}.mp4"))

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bestvideo[height<=1080]+bestaudio/best',  # HD quality, max 1080p video
        'noplaylist': True,
        'socket_timeout': 10,
        'retries': 5,
        'quiet': False,
        'nocheckcertificate': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            file_size = info_dict.get("filesize", 0)
            return file_path, file_size
    except Exception as e:
        logger.error(f"yt-dlp failed: {e}")
        return download_video_pytube(url)


def download_video_pytube(url):
    """
    Alternative download method using pytube.
    """
    try:
        yt = YouTube(url)
        stream = yt.streams.get_highest_resolution()
        file_path = os.path.join(DOWNLOAD_DIR, sanitize_filename(f"{yt.title}.mp4"))
        stream.download(output_path=DOWNLOAD_DIR, filename=sanitize_filename(yt.title) + ".mp4")
        return file_path, os.path.getsize(file_path)
    except Exception as e:
        logger.error(f"Pytube failed: {e}")
        return None, 0


def convert_video_to_audio(video_path):
    """
    Converts a downloaded video to an MP3 file using ffmpeg.
    """
    try:
        audio_path = video_path.replace(".mp4", ".mp3")
        ffmpeg.input(video_path).output(audio_path, format="mp3").run()
        return audio_path
    except Exception as e:
        logger.error(f"Error converting video to MP3: {e}")
        return None


def fetch_video_metadata(url):
    """
    Fetches video title, duration, and thumbnail using yt-dlp.
    """
    try:
        ydl_opts = {"quiet": True, "extract_flat": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            return {
                "title": info_dict.get("title"),
                "duration": info_dict.get("duration"),
                "thumbnail": info_dict.get("thumbnail"),
            }
    except Exception as e:
        logger.error(f"Error fetching metadata: {e}")
        return None


def download_video_thumbnail(url):
    """
    Downloads the video thumbnail using requests.
    """
    metadata = fetch_video_metadata(url)
    if metadata and metadata.get("thumbnail"):
        try:
            response = requests.get(metadata["thumbnail"], stream=True)
            if response.status_code == 200:
                thumb_path = os.path.join(DOWNLOAD_DIR, "thumbnail.jpg")
                with open(thumb_path, "wb") as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                return thumb_path
        except Exception as e:
            logger.error(f"Error downloading thumbnail: {e}")
    return None


# Example Usage
if __name__ == "__main__":
    youtube_url = "https://www.youtube.com/watch?v=XYZ123"  # Replace with actual URL

    # Download video
    video_path, size = process_youtube(youtube_url)
    print(f"Downloaded: {video_path} (Size: {size} bytes)")

    # Convert to audio
    audio_path = convert_video_to_audio(video_path)
    if audio_path:
        print(f"Audio saved at: {audio_path}")

    # Fetch metadata
    metadata = fetch_video_metadata(youtube_url)
    if metadata:
        print(f"Title: {metadata['title']}, Duration: {metadata['duration']}s")

    # Download thumbnail
    thumbnail_path = download_video_thumbnail(youtube_url)
    if thumbnail_path:
        print(f"Thumbnail saved at: {thumbnail_path}")