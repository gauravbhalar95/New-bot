import os
from moviepy.editor import VideoFileClip

def generate_thumbnail(video_path):
    thumbnail_path = video_path.replace(".mp4", "_thumb.jpg")
    try:
        clip = VideoFileClip(video_path)
        frame = clip.get_frame(clip.duration / 2)
        clip.save_frame(thumbnail_path, t=clip.duration / 2)
        clip.close()
        return thumbnail_path
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return "templates/thumbnail.jpg"  # Default fallback
