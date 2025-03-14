import asyncio
import subprocess
import os

async def compress_video(input_path):
    """
    Compresses a video using `ffmpeg` with optimized settings for quality retention.
    """
    output_path = f"{os.path.splitext(input_path)[0]}_compressed.mp4"

    command = [
        'ffmpeg', '-y', '-i', input_path,
        '-c:v', 'libx264',            # Use H.264 codec for high efficiency
        '-crf', '23',                 # Constant Rate Factor (balanced quality/compression)
        '-preset', 'slow',            # Better compression with reasonable encoding speed
        '-c:a', 'aac',                # Audio codec for compatibility
        '-b:a', '128k',               # Audio bitrate for quality retention
        '-movflags', '+faststart',    # Optimizes file for streaming
        output_path
    ]

    try:
        loop = asyncio.get_running_loop()
        process = await loop.run_in_executor(None, subprocess.run, command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if process.returncode == 0 and os.path.exists(output_path):
            return output_path
        else:
            return None
    except Exception as e:
        print(f"⚠️ Compression error: {e}")
        return None