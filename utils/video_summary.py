import whisper
import os

# Load Whisper AI model
model = whisper.load_model("small")

def generate_summary(video_path):
    """Generates a short AI-based summary of the video's audio content."""
    try:
        # Convert audio from video (Extracting audio)
        audio_path = video_path.replace(".mp4", ".wav")
        os.system(f"ffmpeg -i {video_path} -ar 16000 -ac 1 -q:a 3 {audio_path} -y")

        # Transcribe audio to text
        result = model.transcribe(audio_path)
        transcript = result["text"]

        # Generate a summary (Simple text trimming for now)
        summary = " ".join(transcript.split()[:50]) + "..."

        # Cleanup audio file
        os.remove(audio_path)

        return summary
    except Exception as e:
        print(f"Error in summarization: {e}")
        return "❌ Unable to generate a summary."