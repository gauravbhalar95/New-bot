import yt_dlp
from utils.sanitize import sanitize_filename
from utils.thumb_generator import generate_thumbnail

    ydl_opts = {
    "format": "best",
    "outtmpl": f"{DOWNLOAD_DIR}/{sanitize_filename('%(title)s')}.%(ext)s",
    "retries": 5,
    "socket_timeout": 10,
    "noplaylist": True,
    "cookiefile": "COOKIES_FILE",  # Ensure this file is updated
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
    },
}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            file_size = info_dict.get("filesize", 0)

            # Download thumbnail
            thumb_url = info_dict.get("thumbnail")
            thumb_path = download_thumbnail(thumb_url, file_path) if thumb_url else None

            return file_path, file_size, thumb_path

    except Exception as e:
        logger.error(f"Error downloading YouTube video: {e}")
        return None, 0, None