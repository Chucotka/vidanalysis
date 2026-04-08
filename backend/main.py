from fastapi import FastAPI, File, UploadFile, BackgroundTasks, Form, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import yt_dlp
import uuid
import os
import asyncio
import json
import csv
import io
import time

from backend.config import settings
from backend.database import engine, Base, get_db, init_db
from backend.models import Job, Timecode
from backend.tasks import analyze_video_task
from backend.dependencies import verify_auth_token

app = FastAPI(title="CineTimecode")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.STORAGE_PATH, exist_ok=True)
os.makedirs(os.path.join(settings.STORAGE_PATH, "thumbnails"), exist_ok=True)

# Note: We will use FileResponse with byte-range requests directly for video playing,
# but we can mount the whole storage for thumbnails.
app.mount("/static", StaticFiles(directory=settings.STORAGE_PATH), name="static")

scheduler = AsyncIOScheduler()

async def cleanup_old_files():
    print("Running 24h cleanup task...")
    now = time.time()
    cutoff = now - (24 * 3600)

    async with engine.begin() as conn:
        from sqlalchemy import text
        # Only cleanup files, keep db records if you want, or delete old jobs.
        # Requirements say: Delete both source video and thumbnails. Keep analysis JSON in DB.
        # We can just iterate over the storage dir and check file ages.
        pass

    for root, dirs, files in os.walk(settings.STORAGE_PATH, topdown=False):
        for file in files:
            if file == "cinetimecode.db" or file.endswith("-journal"):
                continue
            path = os.path.join(root, file)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    print(f"Deleted old file: {path}")
            except Exception as e:
                print(f"Error deleting file {path}: {e}")

        for d in dirs:
            dir_path = os.path.join(root, d)
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    print(f"Deleted empty directory: {dir_path}")
            except Exception as e:
                print(f"Error deleting directory {dir_path}: {e}")

@app.on_event("startup")
async def startup_event():
    await init_db()
    scheduler.add_job(cleanup_old_files, 'interval', hours=1)
    scheduler.start()

@app.post("/api/analyze", dependencies=[Depends(verify_auth_token)])
async def analyze_video(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    content_type = request.headers.get("content-type", "")
    file = None
    video_url = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        video_url = form.get("video_url")
    elif "application/json" in content_type:
        body = await request.json()
        video_url = body.get("url") or body.get("video_url")
    else:
        raise HTTPException(status_code=400, detail="Invalid Content-Type")

    if not file and not video_url:
        raise HTTPException(status_code=400, detail="Must provide either file or video_url")

    job_id = str(uuid.uuid4())
    video_path = ""
    original_filename = ""

    if file and hasattr(file, "filename"):
        original_filename = file.filename
        ext = os.path.splitext(original_filename)[1]
        video_path = os.path.join(settings.STORAGE_PATH, f"{job_id}{ext}")
        with open(video_path, "wb") as buffer:
            while content := await file.read(1024 * 1024):
                buffer.write(content)
    elif video_url:
        original_filename = video_url
        video_path = os.path.join(settings.STORAGE_PATH, f"{job_id}.mp4")

    new_job = Job(id=job_id, video_path=video_path, original_filename=original_filename)
    db.add(new_job)
    await db.commit()

    # Start Celery task
    # Pass video_url if it's a URL download, so the worker can handle it.
    analyze_video_task.delay(job_id, video_path, video_url)

    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}/status", dependencies=[Depends(verify_auth_token)])
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "status": job.status,
        "progress": job.progress,
        "current_step": job.current_step,
        "error_message": job.error_message
    }

@app.get("/api/jobs/{job_id}/stream", dependencies=[Depends(verify_auth_token)])
async def stream_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    async def event_generator():
        last_progress = -1
        last_step = ""
        while True:
            # Create a new session for each poll to get fresh data
            async with engine.connect() as conn:
                from sqlalchemy import text
                result = await conn.execute(text("SELECT status, progress, current_step, error_message FROM jobs WHERE id = :id"), {"id": job_id})
                row = result.fetchone()

                if not row:
                    yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                    break

                status, progress, current_step, error_message = row

                if progress != last_progress or current_step != last_step:
                    data = {
                        "status": status,
                        "progress": progress,
                        "step": current_step,
                        "error": error_message
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                    last_progress = progress
                    last_step = current_step

                if status in ["complete", "error"]:
                    break

            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/jobs/{job_id}/timecodes", dependencies=[Depends(verify_auth_token)])
async def get_timecodes(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Timecode).where(Timecode.job_id == job_id).order_by(Timecode.scene_number))
    timecodes = result.scalars().all()

    def format_time(seconds: float):
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    output = []
    for tc in timecodes:
        output.append({
            "start": format_time(tc.start_time),
            "end": format_time(tc.end_time),
            "start_seconds": tc.start_time,
            "end_seconds": tc.end_time,
            "duration": tc.duration,
            "scene_number": tc.scene_number,
            "type": tc.event_type,
            "description": tc.description,
            "dialogue_excerpt": tc.dialogue_excerpt,
            "thumbnail_url": f"/static/{tc.thumbnail_path}" if tc.thumbnail_path else None
        })

    return output

@app.get("/api/jobs/{job_id}/export", dependencies=[Depends(verify_auth_token)])
async def export_timecodes(job_id: str, format: str = "json", db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Timecode).where(Timecode.job_id == job_id).order_by(Timecode.scene_number))
    timecodes = result.scalars().all()

    def format_time(seconds: float):
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    data = []
    for tc in timecodes:
        data.append({
            "start": format_time(tc.start_time),
            "end": format_time(tc.end_time),
            "duration": round(tc.duration, 2),
            "scene_number": tc.scene_number,
            "type": tc.event_type,
            "description": tc.description,
            "dialogue_excerpt": tc.dialogue_excerpt
        })

    if format == "json":
        return JSONResponse(content=data)
    elif format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["start", "end", "duration", "scene_number", "type", "description", "dialogue_excerpt"])
        writer.writeheader()
        writer.writerows(data)

        response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=timecodes_{job_id}.csv"
        return response
    elif format == "txt":
        output = ""
        for tc in data:
            output += f"{tc['start']} {tc['type']} - {tc['description']}\n"
        response = StreamingResponse(iter([output]), media_type="text/plain")
        response.headers["Content-Disposition"] = f"attachment; filename=chapters_{job_id}.txt"
        return response
    else:
        raise HTTPException(status_code=400, detail="Invalid format")

@app.get("/api/jobs/{job_id}/video", dependencies=[Depends(verify_auth_token)])
async def get_video(job_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalars().first()

    if not job or not job.video_path or not os.path.exists(job.video_path):
        raise HTTPException(status_code=404, detail="Video not found")

    # FileResponse natively supports Range headers in FastAPI/Starlette
    return FileResponse(
        path=job.video_path,
        media_type="video/mp4",
        filename=job.original_filename,
        stat_result=os.stat(job.video_path)
    )
