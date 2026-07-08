from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisRecord


class AnalysisRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, analysis_id: int, *, user_id: int) -> AnalysisRecord | None:
        return self.db.scalar(
            select(AnalysisRecord)
            .where(AnalysisRecord.id == analysis_id, AnalysisRecord.user_id == user_id)
            .limit(1)
        )

    def add(self, record: AnalysisRecord) -> AnalysisRecord:
        self.db.add(record)
        self.db.flush()
        return record

    def save(self, record: AnalysisRecord) -> AnalysisRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
