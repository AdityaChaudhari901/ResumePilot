from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ResumeRecord


class ResumeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, resume_id: int, *, user_id: int) -> ResumeRecord | None:
        return self.db.scalar(
            select(ResumeRecord)
            .where(ResumeRecord.id == resume_id, ResumeRecord.user_id == user_id)
            .limit(1)
        )

    def get_by_file_hash(self, file_hash: str, *, user_id: int) -> ResumeRecord | None:
        return self.db.scalar(
            select(ResumeRecord)
            .where(ResumeRecord.file_hash == file_hash, ResumeRecord.user_id == user_id)
            .limit(1)
        )

    def latest(self, *, user_id: int) -> ResumeRecord | None:
        return self.db.scalar(
            select(ResumeRecord)
            .where(ResumeRecord.user_id == user_id)
            .order_by(ResumeRecord.created_at.desc(), ResumeRecord.id.desc())
            .limit(1)
        )

    def add(self, record: ResumeRecord) -> ResumeRecord:
        self.db.add(record)
        self.db.flush()
        return record

    def save(self, record: ResumeRecord) -> ResumeRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
