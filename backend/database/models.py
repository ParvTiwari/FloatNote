from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from datetime import datetime
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE_PATH = os.path.join(BASE_DIR, "meeting_assistant.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DB_FILE_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, default="Test Meeting")
    start_time = Column(DateTime, default=datetime.utcnow)
    summary = Column(Text, nullable=True) 

class Transcript(Base):
    __tablename__ = "transcripts"
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    text = Column(Text, nullable=False)
    keywords = Column(String)
    source = Column(String, default="unknown", index=True) 

class ActionItem(Base):
    __tablename__ = "action_items"
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    description = Column(String, nullable=False)
    assignee = Column(String, default="unassigned") 
    status = Column(String, default="pending")