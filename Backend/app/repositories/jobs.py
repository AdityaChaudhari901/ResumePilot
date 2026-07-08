from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import JobRecord


class JobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, job_id: int) -> JobRecord | None:
        return self.db.get(JobRecord, job_id)

    def get_by_content_hash(self, content_hash: str) -> JobRecord | None:
        return self.db.scalar(select(JobRecord).where(JobRecord.content_hash == content_hash))

    def add(self, record: JobRecord) -> JobRecord:
        self.db.add(record)
        self.db.flush()
        return record

    def save(self, record: JobRecord) -> JobRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
