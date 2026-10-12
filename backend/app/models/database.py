"""SQLite Database setup and models using SQLAlchemy (Phase 4)."""

import json
from datetime import datetime
from typing import Generator, Optional
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    inspect,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from app.core.config import settings

# SQLite connection
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """User account model for authentication and summary ownership."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    summaries = relationship("SummaryRecord", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SummaryRecord(Base):
    """Database model for storing processed email thread summaries associated with an owning user."""

    __tablename__ = "email_summaries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    content_hash = Column(String(64), index=True, nullable=True)
    schema_version = Column(String(20), default="v3", nullable=True)
    subject = Column(String(255), nullable=True)
    raw_content_preview = Column(String(500), nullable=False)
    original_content = Column(Text, nullable=True)
    summary_json = Column(Text, nullable=False)
    model_used = Column(String(100), nullable=False)
    char_count = Column(Integer, nullable=False)
    processing_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="summaries")

    def get_summary_dict(self) -> dict:
        """Return parsed JSON summary dictionary."""
        try:
            return json.loads(self.summary_json)
        except Exception:
            return {}

    def to_dict(self) -> dict:
        """Convert database record to dictionary representation."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "subject": self.subject or "Untitled Email Thread",
            "raw_preview": self.raw_content_preview,
            "original_content": self.original_content,
            "summary": self.get_summary_dict(),
            "model_used": self.model_used,
            "char_count": self.char_count,
            "processing_time_ms": self.processing_time_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def init_db() -> None:
    """Create database tables and apply backward-compatible schema migrations."""
    Base.metadata.create_all(bind=engine)

    # Ensure backward-compatibility: add new columns if table was created previously
    inspector = inspect(engine)
    if "email_summaries" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("email_summaries")]
        with engine.connect() as conn:
            if "content_hash" not in columns:
                conn.execute(text("ALTER TABLE email_summaries ADD COLUMN content_hash VARCHAR(64)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_email_summaries_content_hash ON email_summaries (content_hash)"))
                conn.commit()
            if "original_content" not in columns:
                conn.execute(text("ALTER TABLE email_summaries ADD COLUMN original_content TEXT"))
                conn.commit()
            if "schema_version" not in columns:
                conn.execute(text("ALTER TABLE email_summaries ADD COLUMN schema_version VARCHAR(20) DEFAULT 'v1'"))
                conn.commit()
            if "user_id" not in columns:
                conn.execute(text("ALTER TABLE email_summaries ADD COLUMN user_id INTEGER"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_email_summaries_user_id ON email_summaries (user_id)"))
                conn.commit()


def get_db() -> Generator[Session, None, None]:
    """Dependency for providing database session to route handlers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
