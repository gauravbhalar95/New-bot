import yt_dlp
from utils.sanitize import sanitize_filename
from utils.thumb_generator import generate_thumbnail

def process_youtube(url):
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'downloads/{sanitize_filename("%(title)s")}.%(ext)s',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            file_size = info_dict.get('filesize', 0)
            thumb_path = generate_thumbnail(file_path)
            return file_path, file_size, thumb_path
    except Exception as e:
        print(f"Error downloading YouTube video: {e}")
        return None, 0, None