import os
import re
import cloudscraper
import telebot
from moviepy import VideoFileClip
from config import API_TOKEN  # ✅ Import API Token from config

bot = telebot.TeleBot(API_TOKEN)

# ✅ Headers for requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Connection": "keep-alive"
}

scraper = cloudscraper.create_scraper()

# ✅ Function to generate a thumbnail from the video
def generate_thumbnail(video_path):
    try:
        clip = VideoFileClip(video_path)
        thumbnail_path = video_path.replace(".mp4", ".jpg")
        clip.save_frame(thumbnail_path, t=clip.duration / 2)  # Take a frame from the middle
        clip.close()
        return thumbnail_path
    except Exception as e:
        print(f"❌ Thumbnail Error: {e}")
        return None

# ✅ Function to process adult video downloads
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

    return None, None, None  # Return three values

# ✅ Extract Video ID
def extract_video_id(url, site):
    patterns = {
        "xvideos": r"xvideos\.com/video(?:/|\.php\?v=)?(\d+)",
        "xnxx": r"xnxx\.com/video-([a-zA-Z0-9]+)",
        "xhamster": r"xhamster\.com/videos/([a-zA-Z0-9-]+)",
        "pornhub": r"(?:viewkey=|embed/)([a-zA-Z0-9_-]+)",
        "redtube": r"redtube\.com/([0-9]+)"
    }

    pattern = patterns.get(site)
    if not pattern:
        return None

    match = re.search(pattern, url)
    return match.group(1) if match else None

# ✅ Get Video Download Link
def get_video_download_link(video_page_url, regex_patterns):
    response = scraper.get(video_page_url, headers=HEADERS)
    if response.status_code != 200:
        return None

    for pattern in regex_patterns:
        match = re.search(pattern, response.text)
        if match:
            return match.group(1)

    return None

# ✅ Download Video
def download_video(url, site, regex_patterns):
    try:
        video_id = extract_video_id(url, site)
        if not video_id:
            return None, None, None

        video_url = get_video_download_link(url, regex_patterns)
        if not video_url:
            return None, None, None

        temp_path = f"{site}_{video_id}_temp.mp4"
        final_path = f"{site}_{video_id}.mp4"

        # ✅ Download video
        response = scraper.get(video_url, headers=HEADERS, stream=True)
        response.raise_for_status()

        with open(temp_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        # ✅ Convert video with MoviePy
        try:
            clip = VideoFileClip(temp_path)
            clip.write_videofile(final_path, codec="libx264")
            clip.close()
            os.remove(temp_path)  # Delete temp file

        except Exception as e:
            return None, None, None

        file_size = os.path.getsize(final_path)
        thumb_path = generate_thumbnail(final_path)  # ✅ Generate thumbnail
        return final_path, file_size, thumb_path

    except Exception as e:
        return None, None, None

# ✅ Site-specific download functions
def download_xvideos(url):
    return download_video(url, "xvideos", [r'"videoUrl":"(https?://[^"]+)"'])

def download_xnxx(url):
    return download_video(url, "xnxx", [r'"videoUrl":"(https?://[^"]+)"'])

def download_xhamster(url):
    return download_video(url, "xhamster", [r'"videoUrl":"(https?://[^"]+)"'])

def download_pornhub(url):
    return download_video(url, "pornhub", [r'"videoUrl":"(https?://[^"]+)"'])

def download_redtube(url):
    return download_video(url, "redtube", [r'"videoUrl":"(https?://[^"]+)"'])

# ✅ Telegram Bot Handlers
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.reply_to(message, "🔹 Send me a video link from **XVideos, XNXX, XHamster, Pornhub, RedTube**, and I'll download it for you!")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()

    # ✅ Check if URL is valid
    if not any(site in url for site in ["xvideos.com", "xnxx.com", "xhamster.com", "pornhub.com", "redtube.com"]):
        bot.reply_to(message, "❌ Invalid URL. Please send a valid video link from **XVideos, XNXX, XHamster, Pornhub, or RedTube**.")
        return

    bot.reply_to(message, "🔄 Downloading... Please wait.")

    # ✅ Process the video
    file_path, file_size, thumb_path = process_adult(url)

    if file_path:
        with open(file_path, 'rb') as video_file:
            if thumb_path:
                with open(thumb_path, 'rb') as thumb:
                    bot.send_video(
                        message.chat.id,
                        video_file,
                        caption=f"✅ Downloaded: {file_path} ({file_size / (1024 * 1024):.2f} MB)",
                        thumb=thumb
                    )
                os.remove(thumb_path)  # Delete thumbnail
            else:
                bot.send_video(
                    message.chat.id,
                    video_file,
                    caption=f"✅ Downloaded: {file_path} ({file_size / (1024 * 1024):.2f} MB)"
                )
        os.remove(file_path)  # Delete after sending
    else:
        bot.reply_to(message, "❌ Failed to download video. Please try another link.")

