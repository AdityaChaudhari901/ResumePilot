from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class ResumeRecord(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_extension: Mapped[str] = mapped_column(String(32))
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    profile_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    candidate_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    analyses: Mapped[list["AnalysisRecord"]] = relationship(back_populates="resume")


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    profile_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    analyses: Mapped[list["AnalysisRecord"]] = relationship(back_populates="job")


class AnalysisRecord(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    status: Mapped[str] = mapped_column(String(64), default="completed")
    match_score: Mapped[float] = mapped_column(Float)
    match_result_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    report_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    report_markdown: Mapped[str] = mapped_column(Text)
    validation_warnings_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    resume: Mapped[ResumeRecord] = relationship(back_populates="analyses")
    job: Mapped[JobRecord] = relationship(back_populates="analyses")


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
