import os
import sys
import os
import asyncio
import yt_dlp
import logging
from utils.sanitize import sanitize_filename
from config import YOUTUBE_FILE, DOWNLOAD_DIR
from utils.logger import setup_logging

logger = setup_logging(logging.DEBUG)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


async def extract_url_and_time(text):
    """Regex નો ઉપયોગ કરીને URL અને Start/End Time એક્સટ્રાક્ટ કરો"""
    match = re.match(r"(https?://[^\s]+)\s+(\d+)\s+(\d+)", text)
    if match:
        return match.groups()
    return None, None, None

async def download_youtube_video(url):
    """YouTube વિડિઓ Async ડાઉનલોડ કરો"""
    ydl_opts = {
        'format': 'best',
        'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
        'merge_output_format': 'mp4',
        'quiet': True,
    }
    loop = asyncio.get_running_loop()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
        return ydl.prepare_filename(info).replace('.webm', '.mp4')

async def trim_video(input_path, start_time, end_time):
    """FFmpeg Async Command Execution"""
    output_path = input_path.replace(".mp4", "_trimmed.mp4")
    cmd = ["ffmpeg", "-y", "-i", input_path, "-ss", str(start_time), "-to", str(end_time), "-c", "copy", output_path]
    
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()
    
    return output_path if process.returncode == 0 else None

async def process_youtube_request(text):
    """Async Function to Process YouTube Download & Trim"""
    url, start, end = await extract_url_and_time(text)
    if not url:
        return "❌ **Invalid Format.** Please send: `<YouTube URL> <Start Time in sec> <End Time in sec>`"
    
    logging.info(f"Processing: {url}, Start: {start}s, End: {end}s")
    
    video_path = await download_youtube_video(url)
    if video_path:
        trimmed_path = await trim_video(video_path, start, end)
        return f"✅ **Trimmed Video Ready:** `{trimmed_path}`" if trimmed_path else "❌ **Trimming Failed.**"
    return "❌ **Download Failed.**"