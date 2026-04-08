import os
import subprocess
from scenedetect import detect, ContentDetector

def detect_scenes(video_path: str, threshold: float = 27.0):
    scene_list = detect(video_path, ContentDetector(threshold=threshold))
    return scene_list

def extract_thumbnail(video_path: str, time_sec: float, output_path: str):
    command = [
        "ffmpeg",
        "-y",
        "-ss", str(time_sec),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        output_path
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
