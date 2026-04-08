from celery import Celery
import asyncio
from backend.config import settings
from backend.analyzer import analyze_video_pipeline

celery_app = Celery("tasks", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

@celery_app.task(name="analyze_video")
def analyze_video_task(job_id: str, video_path: str, video_url: str = None):
    # Run the async pipeline in a synchronous celery task safely
    asyncio.run(analyze_video_pipeline(job_id, video_path, video_url))
