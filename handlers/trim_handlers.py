import os
import re
import asyncio
import yt_dlp
import logging
import subprocess
from utils.sanitize import sanitize_filename
from config import DOWNLOAD_DIR, YOUTUBE_FILE
from utils.logger import setup_logging

# Setup logging
logger = setup_logging(logging.DEBUG)

# Ensure the download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def time_to_seconds(time_str):
    """
    Converts time string to seconds.
    Supports HH:MM:SS, MM:SS, and SS formats.
    """
    try:
        parts = time_str.split(":")
        if len(parts) == 3:  # HH:MM:SS
            h, m, s = map(int, parts)
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:  # MM:SS
            m, s = map(int, parts)
            return m * 60 + s
        elif len(parts) == 1:  # SS
            return int(parts[0])
        else:
            logger.error(f"Invalid time format: {time_str}")
            return None
    except ValueError as e:
        logger.error(f"Time conversion error for '{time_str}': {e}")
        return None

async def download_media(url, is_audio=False):
    """
    Downloads video or audio using yt-dlp.
    
    Args:
        url (str): URL of the media to download
        is_audio (bool): Whether to download as audio only
        
    Returns:
        str: Path to the downloaded file or None if download failed
    """
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s_%(id)s.%(ext)s")

    # Set different options based on whether we're downloading audio or video
    if is_audio:
        ydl_opts = {
            'format': 'bestaudio',
            'outtmpl': output_path,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
            'quiet': False,
            'noplaylist': True,
        }
    else:
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': output_path,
            'merge_output_format': 'mp4',
            'cookiefile': YOUTUBE_FILE if os.path.exists(YOUTUBE_FILE) else None,
            'quiet': False,
            'noplaylist': True,
        }

    loop = asyncio.get_running_loop()
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            file_path = ydl.prepare_filename(info)

            # Ensure correct file extension
            if is_audio:
                file_path = file_path.rsplit(".", 1)[0] + ".mp3"
            else:
                # Check if the file exists with mp4 extension, otherwise try original extension
                mp4_path = file_path.rsplit(".", 1)[0] + ".mp4"
                if os.path.exists(mp4_path):
                    file_path = mp4_path
                elif not os.path.exists(file_path):
                    # Check for any file with the same base name
                    base_name = file_path.rsplit(".", 1)[0]
                    for file in os.listdir(DOWNLOAD_DIR):
                        if file.startswith(os.path.basename(base_name)):
                            file_path = os.path.join(DOWNLOAD_DIR, file)
                            break

            logger.debug(f"Downloaded file path: {file_path}")
            return file_path if os.path.exists(file_path) else None
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Error downloading media: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during download: {str(e)}", exc_info=True)
        return None

async def trim_video(input_path, start_time, end_time):
    """
    Trims a video file using ffmpeg.
    
    Args:
        input_path (str): Path to the video file
        start_time (int): Start time in seconds
        end_time (int): End time in seconds
        
    Returns:
        tuple: (file_path, file_size) if successful, or (None, None) if failed
    """
    if not os.path.exists(input_path):
        logger.error(f"Input file does not exist: {input_path}")
        return None, None
        
    output_path = input_path.rsplit(".", 1)[0] + f"_trim_{start_time}_{end_time}.mp4"

    # Check if ffmpeg is installed
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.error("FFmpeg not found. Please install FFmpeg.")
        return None, None

    command = [
        "ffmpeg", "-i", input_path, 
        "-ss", str(start_time), 
        "-to", str(end_time),
        "-c:v", "libx264", 
        "-c:a", "aac", 
        "-preset", "fast",
        "-y", output_path
    ]

    logger.debug(f"Running FFmpeg video trim command: {' '.join(command)}")

    try:
        process = await asyncio.create_subprocess_exec(
            *command, 
            stdout=asyncio.subprocess.PIPE, 
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            logger.info(f"Video trimming successful. Output file: {output_path}, Size: {file_size} bytes")
            return output_path, file_size
        else:
            logger.error(f"FFmpeg video trim error (return code {process.returncode}): {stderr.decode()}")
            # Try alternative approach
            return await trim_video_alternative(input_path, start_time, end_time)
    except Exception as e:
        logger.error(f"Exception during video trim: {str(e)}", exc_info=True)
        return None, None

async def trim_video_alternative(input_path, start_time, end_time):
    """Alternative video trimming method that uses a different FFmpeg approach"""
    output_path = input_path.rsplit(".", 1)[0] + f"_trim_alt_{start_time}_{end_time}.mp4"
    
    # Different FFmpeg command that may work in some cases where the other fails
    command = [
        "ffmpeg",
        "-ss", str(start_time),  # Place -ss before -i for faster seeking
        "-i", input_path,
        "-t", str(end_time - start_time),  # Duration instead of end time
        "-c", "copy",  # Use stream copy (no re-encoding, faster but less precise)
        "-y", output_path
    ]
    
    logger.debug(f"Running alternative FFmpeg video trim command: {' '.join(command)}")
    
    try:
        process = await asyncio.create_subprocess_exec(
            *command, 
            stdout=asyncio.subprocess.PIPE, 
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            logger.info(f"Alternative video trimming successful. Output file: {output_path}, Size: {file_size} bytes")
            return output_path, file_size
        else:
            logger.error(f"Alternative FFmpeg video trim error (return code {process.returncode}): {stderr.decode()}")
            return None, None
    except Exception as e:
        logger.error(f"Exception during alternative video trim: {str(e)}", exc_info=True)
        return None, None

async def trim_audio(input_path, start_time, end_time):
    """
    Trims an audio file using ffmpeg.
    
    Args:
        input_path (str): Path to the audio file
        start_time (int): Start time in seconds
        end_time (int): End time in seconds
        
    Returns:
        tuple: (file_path, file_size) if successful, or (None, None) if failed
    """
    if not os.path.exists(input_path):
        logger.error(f"Input file does not exist: {input_path}")
        return None, None
        
    output_path = input_path.rsplit(".", 1)[0] + f"_trim_{start_time}_{end_time}.mp3"

    # Check if ffmpeg is installed
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.error("FFmpeg not found. Please install FFmpeg.")
        return None, None

    command = [
        "ffmpeg", "-i", input_path, 
        "-ss", str(start_time), 
        "-to", str(end_time),
        "-acodec", "libmp3lame", 
        "-q:a", "2",
        "-y", output_path
    ]

    logger.debug(f"Running FFmpeg audio trim command: {' '.join(command)}")

    try:
        process = await asyncio.create_subprocess_exec(
            *command, 
            stdout=asyncio.subprocess.PIPE, 
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            logger.info(f"Audio trimming successful. Output file: {output_path}, Size: {file_size} bytes")
            return output_path, file_size
        else:
            logger.error(f"FFmpeg audio trim error (return code {process.returncode}): {stderr.decode()}")
            # Try alternative approach
            return await trim_audio_alternative(input_path, start_time, end_time)
    except Exception as e:
        logger.error(f"Exception during audio trim: {str(e)}", exc_info=True)
        return None, None

async def trim_audio_alternative(input_path, start_time, end_time):
    """Alternative audio trimming method that uses a different FFmpeg approach"""
    output_path = input_path.rsplit(".", 1)[0] + f"_trim_alt_{start_time}_{end_time}.mp3"
    
    # Different FFmpeg command that may work in some cases where the other fails
    command = [
        "ffmpeg",
        "-ss", str(start_time),  # Place -ss before -i for faster seeking
        "-i", input_path,
        "-t", str(end_time - start_time),  # Duration instead of end time
        "-acodec", "copy",  # Use stream copy (no re-encoding, faster but less precise)
        "-y", output_path
    ]
    
    logger.debug(f"Running alternative FFmpeg audio trim command: {' '.join(command)}")
    
    try:
        process = await asyncio.create_subprocess_exec(
            *command, 
            stdout=asyncio.subprocess.PIPE, 
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            logger.info(f"Alternative audio trimming successful. Output file: {output_path}, Size: {file_size} bytes")
            return output_path, file_size
        else:
            logger.error(f"Alternative FFmpeg audio trim error (return code {process.returncode}): {stderr.decode()}")
            return None, None
    except Exception as e:
        logger.error(f"Exception during alternative audio trim: {str(e)}", exc_info=True)
        return None, None

async def process_video_trim(url, start_time, end_time):
    """
    Process a video trim request - downloads video and trims it.
    
    Args:
        url (str): URL of the video to download and trim
        start_time (str): Start time in HH:MM:SS format
        end_time (str): End time in HH:MM:SS format
        
    Returns:
        tuple: (file_path, file_size) if successful, or (None, None) if failed
    """
    try:
        # Convert time format if necessary
        start_seconds = time_to_seconds(start_time) if isinstance(start_time, str) else start_time
        end_seconds = time_to_seconds(end_time) if isinstance(end_time, str) else end_time

        logger.debug(f"Time conversion results - start_time: '{start_time}' → {start_seconds}s, end_time: '{end_time}' → {end_seconds}s")

        if start_seconds is None or end_seconds is None:
            logger.error("Invalid time format for video trim")
            return None, None

        if start_seconds >= end_seconds:
            logger.error(f"Invalid video trim range: Start time ({start_seconds}s) must be less than end time ({end_seconds}s)")
            return None, None

        # Download the video
        logger.info(f"Downloading video for trimming from: {url}")
        video_path = await download_media(url, is_audio=False)

        if not video_path:
            logger.error("Failed to download video for trimming")
            return None, None

        # Get original file size for logging
        orig_size = os.path.getsize(video_path)
        logger.info(f"Downloaded video file: {video_path}, Size: {orig_size} bytes")

        # Trim the video
        logger.info(f"Trimming video: Start: {start_seconds}s, End: {end_seconds}s")
        trimmed_path, file_size = await trim_video(video_path, start_seconds, end_seconds)

        # Clean up the original downloaded file
        try:
            os.remove(video_path)
            logger.info(f"Removed original video file: {video_path}")
        except Exception as e:
            logger.warning(f"Could not remove original video file {video_path}: {e}")

        if trimmed_path:
            return trimmed_path, file_size
        else:
            logger.error("Failed to trim video")
            return None, None

    except Exception as e:
        logger.error(f"Error in process_video_trim: {e}", exc_info=True)
        return None, None

async def process_audio_trim(url, start_time, end_time):
    """
    Process an audio trim request - downloads audio and trims it.
    
    Args:
        url (str): URL of the media to download audio from and trim
        start_time (str): Start time in HH:MM:SS format
        end_time (str): End time in HH:MM:SS format
        
    Returns:
        tuple: (file_path, file_size) if successful, or (None, None) if failed
    """
    try:
        # Convert time format if necessary
        start_seconds = time_to_seconds(start_time) if isinstance(start_time, str) else start_time
        end_seconds = time_to_seconds(end_time) if isinstance(end_time, str) else end_time
        
        logger.debug(f"Time conversion results - start_time: '{start_time}' → {start_seconds}s, end_time: '{end_time}' → {end_seconds}s")

        if start_seconds is None or end_seconds is None:
            logger.error("Invalid time format for audio trim")
            return None, None

        if start_seconds >= end_seconds:
            logger.error(f"Invalid audio trim range: Start time ({start_seconds}s) must be less than end time ({end_seconds}s)")
            return None, None

        # Download the audio
        logger.info(f"Downloading audio for trimming from: {url}")
        audio_path = await download_media(url, is_audio=True)

        if not audio_path:
            logger.error("Failed to download audio for trimming")
            return None, None

        # Get original file size for logging
        orig_size = os.path.getsize(audio_path)
        logger.info(f"Downloaded audio file: {audio_path}, Size: {orig_size} bytes")

        # Trim the audio
        logger.info(f"Trimming audio: Start: {start_seconds}s, End: {end_seconds}s")
        trimmed_path, file_size = await trim_audio(audio_path, start_seconds, end_seconds)

        # Clean up the original downloaded file
        try:
            os.remove(audio_path)
            logger.info(f"Removed original audio file: {audio_path}")
        except Exception as e:
            logger.warning(f"Could not remove original audio file {audio_path}: {e}")

        if trimmed_path:
            return trimmed_path, file_size
        else:
            logger.error("Failed to trim audio")
            return None, None

    except Exception as e:
        logger.error(f"Error in process_audio_trim: {e}", exc_info=True)
        return None, None