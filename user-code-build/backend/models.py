import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text
from backend.database import Base

class JobStatus(str, enum.Enum):
    READY = "READY"
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    UNSUBSCRIBED = "UNSUBSCRIBED"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

class SenderAccount(Base):
    __tablename__ = "sender_accounts"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    provider = Column(String, default="mock")
    enabled = Column(Boolean, default=True)
    daily_limit = Column(Integer, default=500)
    sent_today = Column(Integer, default=0)

class Recipient(Base):
    __tablename__ = "recipients"
    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.READY)
    sender_account_id = Column(Integer, ForeignKey("sender_accounts.id"), nullable=True)

class SendJob(Base):
    __tablename__ = "send_jobs"
    id = Column(Integer, primary_key=True)
    recipient_id = Column(Integer, ForeignKey("recipients.id"))
    status = Column(Enum(JobStatus), default=JobStatus.QUEUED)
    attempts = Column(Integer, default=0)
