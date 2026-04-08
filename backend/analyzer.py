import os
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from backend.models import Job, Timecode
from backend.database import async_session
from backend.scene_detector import detect_scenes, extract_thumbnail
from backend.transcriber import transcribe_audio
from backend.describer import describe_scene
import yt_dlp

async def update_job_progress(job_id: str, status: str, progress: int, current_step: str):
    async with async_session() as session:
        stmt = (
            update(Job)
            .where(Job.id == job_id)
            .values(status=status, progress=progress, current_step=current_step)
        )
        await session.execute(stmt)
        await session.commit()

async def analyze_video_pipeline(job_id: str, video_path: str, video_url: str = None):
    try:
        if video_url and not os.path.exists(video_path):
            await update_job_progress(job_id, "processing", 5, "Downloading video...")
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': video_path,
                'quiet': True,
                'no_warnings': True
            }
            # Run yt-dlp in a separate thread so it doesn't block the async loop
            loop = asyncio.get_running_loop()
            try:
                await loop.run_in_executor(None, lambda: _download_video(ydl_opts, video_url))
            except Exception as e:
                # Cleanup partial downloads
                if os.path.exists(video_path):
                    os.remove(video_path)
                for partial_ext in [".part", ".ytdl"]:
                    partial_file = f"{video_path}{partial_ext}"
                    if os.path.exists(partial_file):
                        os.remove(partial_file)
                raise Exception(f"Failed to download video: {e}")

        await update_job_progress(job_id, "processing", 10, "Detecting scenes...")
        scene_list = detect_scenes(video_path)

        await update_job_progress(job_id, "processing", 40, "Transcribing audio...")
        transcripts = transcribe_audio(video_path)

        await update_job_progress(job_id, "processing", 70, "Analyzing scenes...")

        thumbnail_dir = os.path.join(os.getenv("STORAGE_PATH", "./storage"), "thumbnails", job_id)
        os.makedirs(thumbnail_dir, exist_ok=True)

        timecodes = []

        async with async_session() as session:
            for i, scene in enumerate(scene_list):
                start_time = scene[0].get_seconds()
                end_time = scene[1].get_seconds()
                duration = end_time - start_time

                # Middle of the scene for thumbnail
                mid_time = start_time + (duration / 2)
                thumbnail_filename = f"scene_{i+1}.jpg"
                thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)
                extract_thumbnail(video_path, mid_time, thumbnail_path)

                # Gather dialogue for this scene
                scene_dialogue = []
                for segment in transcripts:
                    if segment["start"] >= start_time and segment["start"] < end_time:
                        scene_dialogue.append(segment["text"])

                full_dialogue = " ".join(scene_dialogue)
                context_for_ai = full_dialogue[:300]
                dialogue_excerpt = full_dialogue[:100]

                # Describe scene using GPT-4o
                analysis = describe_scene(thumbnail_path, context_for_ai)

                timecode = Timecode(
                    job_id=job_id,
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration,
                    scene_number=i+1,
                    event_type=analysis.get("tag", "UNKNOWN"),
                    description=analysis.get("description", ""),
                    dialogue_excerpt=dialogue_excerpt,
                    thumbnail_path=f"thumbnails/{job_id}/{thumbnail_filename}"
                )
                session.add(timecode)
                timecodes.append(timecode)

                # Update progress based on scenes
                progress = 70 + int((i / len(scene_list)) * 25)
                await update_job_progress(job_id, "processing", progress, f"Analyzing scene {i+1}/{len(scene_list)}...")

            await session.commit()

        await update_job_progress(job_id, "complete", 100, "Done")

    except Exception as e:
        print(f"Error in pipeline: {e}")
        import traceback
        traceback.print_exc()
        async with async_session() as session:
            stmt = (
                update(Job)
                .where(Job.id == job_id)
                .values(status="error", error_message=str(e), current_step="Error occurred")
            )
            await session.execute(stmt)
            await session.commit()

def _download_video(ydl_opts, video_url):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
