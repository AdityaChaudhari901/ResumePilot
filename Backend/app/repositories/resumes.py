from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ResumeRecord


class ResumeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, resume_id: int) -> ResumeRecord | None:
        return self.db.get(ResumeRecord, resume_id)

    def get_by_file_hash(self, file_hash: str) -> ResumeRecord | None:
        return self.db.scalar(select(ResumeRecord).where(ResumeRecord.file_hash == file_hash))

    def latest(self) -> ResumeRecord | None:
        return self.db.scalar(
            select(ResumeRecord)
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
