from sqlalchemy import Column, String, Float, Integer, Boolean, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True)
    status = Column(String, default="pending")  # pending, processing, complete, error
    progress = Column(Integer, default=0)
    current_step = Column(String, default="")
    video_path = Column(String, nullable=True)
    original_filename = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    timecodes = relationship("Timecode", back_populates="job", cascade="all, delete-orphan")

class Timecode(Base):
    __tablename__ = "timecodes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(String, ForeignKey("jobs.id"), index=True)
    start_time = Column(Float)
    end_time = Column(Float)
    duration = Column(Float)
    scene_number = Column(Integer)
    event_type = Column(String)  # ACTION, DIALOGUE, etc.
    description = Column(Text)
    dialogue_excerpt = Column(Text)
    thumbnail_path = Column(String)

    job = relationship("Job", back_populates="timecodes")
