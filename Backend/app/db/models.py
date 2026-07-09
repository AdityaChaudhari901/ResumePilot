from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


def default_workflow_trace() -> dict[str, Any]:
    return {
        "mode": "deterministic_fallback",
        "steps": [
            {
                "name": "validation_gate",
                "status": "degraded",
                "summary": "Workflow trace was not captured for this analysis.",
            }
        ],
        "validation_warning_codes": [],
    }


class ResumeRecord(Base):
    __tablename__ = "resumes"
    __table_args__ = (UniqueConstraint("user_id", "file_hash", name="uq_resumes_user_file_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_extension: Mapped[str] = mapped_column(String(32))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    profile_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    candidate_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    user: Mapped["UserRecord"] = relationship(back_populates="resumes")
    analyses: Mapped[list["AnalysisRecord"]] = relationship(back_populates="resume")


class JobRecord(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_user_content_hash", "user_id", "content_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    profile_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    user: Mapped["UserRecord"] = relationship(back_populates="jobs")
    analyses: Mapped[list["AnalysisRecord"]] = relationship(back_populates="job")


class AnalysisRecord(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    status: Mapped[str] = mapped_column(String(64), default="completed")
    match_score: Mapped[float] = mapped_column(Float)
    match_result_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    report_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    report_markdown: Mapped[str] = mapped_column(Text)
    validation_warnings_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    workflow_mode: Mapped[str] = mapped_column(String(64), default="deterministic_fallback")
    workflow_trace_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=default_workflow_trace
    )
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    user: Mapped["UserRecord"] = relationship(back_populates="analyses")
    resume: Mapped[ResumeRecord] = relationship(back_populates="analyses")
    job: Mapped[JobRecord] = relationship(back_populates="analyses")


class ApplicationRecord(Base):
    __tablename__ = "applications"
    __table_args__ = (
        Index("ix_applications_user_status_created", "user_id", "status", "created_at"),
        Index("ix_applications_user_report", "user_id", "report_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_job_profile_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    resume_id: Mapped[int | None] = mapped_column(index=True, nullable=True)
    job_id: Mapped[int | None] = mapped_column(index=True, nullable=True)
    analysis_id: Mapped[int | None] = mapped_column(index=True, nullable=True)
    report_id: Mapped[int | None] = mapped_column(index=True, nullable=True)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    user: Mapped["UserRecord"] = relationship(back_populates="applications")


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    user: Mapped["UserRecord | None"] = relationship(back_populates="audit_events")


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan: Mapped[str] = mapped_column(String(64), default="free")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    subscription_status: Mapped[str] = mapped_column(String(64), default="inactive")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    resumes: Mapped[list[ResumeRecord]] = relationship(back_populates="user")
    jobs: Mapped[list[JobRecord]] = relationship(back_populates="user")
    analyses: Mapped[list[AnalysisRecord]] = relationship(back_populates="user")
    applications: Mapped[list[ApplicationRecord]] = relationship(back_populates="user")
    audit_events: Mapped[list[AuditEventRecord]] = relationship(back_populates="user")
    usage_events: Mapped[list["UsageEventRecord"]] = relationship(back_populates="user")


class UsageEventRecord(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        Index("ix_usage_events_user_type_created", "user_id", "event_type", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    quantity: Mapped[int] = mapped_column(default=1)
    cost_estimate_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    user: Mapped[UserRecord] = relationship(back_populates="usage_events")
