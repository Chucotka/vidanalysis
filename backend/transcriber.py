import whisper
import openai
from backend.config import settings

def transcribe_audio(video_path: str):
    if settings.MOCK_AI:
        return [
            {"start": 0.0, "end": 15.0, "text": "Hurry, they're catching up!"},
            {"start": 16.0, "end": 30.0, "text": "I can't go any faster!"}
        ]

    if settings.OPENAI_API_KEY:
        try:
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            with open(video_path, "rb") as audio_file:
                # Note: For large files, Whisper API limits to 25MB.
                # In a real-world scenario, you might need to extract audio first and split it.
                # For simplicity here we just send the file (assuming it's small enough or we accept failures).
                # Actually, let's extract audio first to avoid sending large video files.
                import tempfile
                import subprocess
                import os

                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
                    temp_audio_path = temp_audio.name

                subprocess.run([
                    "ffmpeg", "-y", "-i", video_path, "-vn", "-ar", "16000", "-ac", "1", "-b:a", "64k", temp_audio_path
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

                # Check size, if > 25MB, this simple implementation will fail, but handling chunking is out of scope for MVP
                # unless strictly needed. We will proceed with the extracted audio.

                with open(temp_audio_path, "rb") as extracted_audio:
                    response = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=extracted_audio,
                        response_format="verbose_json",
                        timestamp_granularities=["segment"]
                    )

                os.remove(temp_audio_path)

                segments = []
                for segment in response.segments:
                    segments.append({
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text
                    })
                return segments
        except Exception as e:
            print(f"OpenAI Whisper API failed, falling back to local: {e}")

    # Fallback to local whisper
    model = whisper.load_model("base")
    result = model.transcribe(video_path)
    segments = []
    for segment in result["segments"]:
        segments.append({
            "start": segment["start"],
            "end": segment["end"],
            "text": segment["text"]
        })
    return segments
