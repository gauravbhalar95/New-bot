import asyncio
import subprocess

async def compress_video(input_file, output_file):
    cmd = [
        "ffmpeg", "-i", input_file, 
        "-c:v", "libx264", "-crf", "23", "-preset", "medium", 
        "-c:a", "aac", "-b:a", "128k", 
        output_file
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        print(f"✅ Video compressed successfully: {output_file}")
        return output_file
    else:
        print(f"❌ Compression failed: {stderr.decode().strip()}")
        return None