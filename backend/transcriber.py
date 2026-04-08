import os
import tempfile
import subprocess
import glob
import whisper
import openai
from backend.config import settings

def _transcribe_chunks(client, model_name, chunk_files):
    segments = []
    for i, chunk_path in enumerate(sorted(chunk_files)):
        with open(chunk_path, "rb") as extracted_audio:
            response = client.audio.transcriptions.create(
                model=model_name,
                file=extracted_audio,
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )

        # Audio chunks are 10 minutes (600 seconds) each
        time_offset = i * 600.0

        for segment in response.segments:
            segments.append({
                "start": segment.start + time_offset,
                "end": segment.end + time_offset,
                "text": segment.text
            })
    return segments

def transcribe_audio(video_path: str):
    if settings.MOCK_AI:
        return [
            {"start": 0.0, "end": 10.0, "text": "Hurry, they're catching up!"},
            {"start": 11.0, "end": 20.0, "text": "I can't go any faster!"},
            {"start": 21.0, "end": 30.0, "text": "We have to hide in there."},
            {"start": 31.0, "end": 40.0, "text": "Quiet! They are right outside."},
            {"start": 41.0, "end": 50.0, "text": "Did you hear that explosion?"},
            {"start": 51.0, "end": 60.0, "text": "Yeah, it came from the north."},
            {"start": 61.0, "end": 70.0, "text": "I love you. I know."},
            {"start": 71.0, "end": 80.0, "text": "Hahaha, that was hilarious!"},
            {"start": 81.0, "end": 90.0, "text": "We need to talk about what happened."},
            {"start": 91.0, "end": 100.0, "text": "And so, the journey continues..."}
        ]

    chunk_dir = tempfile.mkdtemp()

    try:
        # Extract and split audio into 10-minute chunks to stay under 25MB limits
        chunk_pattern = os.path.join(chunk_dir, "chunk_%03d.mp3")
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-ar", "16000", "-ac", "1", "-b:a", "64k",
            "-f", "segment", "-segment_time", "600",
            chunk_pattern
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        chunk_files = glob.glob(os.path.join(chunk_dir, "chunk_*.mp3"))

        if settings.GROQ_API_KEY:
            try:
                client = openai.OpenAI(
                    base_url="https://api.groq.com/openai/v1",
                    api_key=settings.GROQ_API_KEY
                )
                return _transcribe_chunks(client, "whisper-large-v3", chunk_files)
            except Exception as e:
                print(f"Groq API failed, falling back to OpenAI: {e}")

        if settings.OPENAI_API_KEY:
            try:
                client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
                return _transcribe_chunks(client, "whisper-1", chunk_files)
            except Exception as e:
                print(f"OpenAI Whisper API failed, falling back to local: {e}")

    except Exception as e:
        print(f"API processing failed: {e}")
    finally:
        for f in glob.glob(os.path.join(chunk_dir, "*")):
            os.remove(f)
        os.rmdir(chunk_dir)

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
