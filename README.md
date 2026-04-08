# CineTimecode

Build a full-stack web application called "CineTimecode" that analyzes any video file
(primarily movies and series) and generates precise, structured timecodes of everything
happening in the video.

## Prerequisites

1. **Docker**: Ensure you have Docker and Docker Compose installed.
2. **FFmpeg**: Required for scene detection and thumbnail extraction.
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
   - Windows: `winget install ffmpeg`

## Environment Setup

You need to provide your OpenAI API key for real analysis. Create a `.env` file in the root directory:

```env
OPENAI_API_KEY=your_actual_key_here
```

If you don't have an API key, the app can run in mock mode by setting `MOCK_AI=true`.

## Running the App

Run the application using Docker Compose:

```bash
docker-compose up --build
```

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`

## Supported Video Formats

- mp4
- mkv
- mov
- avi

## Estimated Processing Time

- Processing takes roughly 15-30% of the video duration depending on scene density and hardware.
- E.g., 1 hour video -> ~10-20 minutes.

## Example Timecode Output

```json
[
  {
    "start": "00:00:00",
    "end": "00:00:15",
    "duration": 15.0,
    "scene_number": 1,
    "type": "TRANSITION",
    "description": "A slow fade into a quiet, misty forest. No one is speaking.",
    "dialogue_excerpt": "",
    "thumbnail_url": "/api/jobs/123/thumbnail/1"
  },
  {
    "start": "00:00:15",
    "end": "00:00:45",
    "duration": 30.0,
    "scene_number": 2,
    "type": "ACTION",
    "description": "Two figures dart between the trees, their faces obscured by the fog.",
    "dialogue_excerpt": "Hurry, they're catching up!",
    "thumbnail_url": "/api/jobs/123/thumbnail/2"
  }
]
```
