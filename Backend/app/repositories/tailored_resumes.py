from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import TailoredResumeDraftRecord


class TailoredResumeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_application_id(
        self, application_id: int, *, user_id: int
    ) -> TailoredResumeDraftRecord | None:
        return self.db.scalar(
            select(TailoredResumeDraftRecord)
            .where(
                TailoredResumeDraftRecord.application_id == application_id,
                TailoredResumeDraftRecord.user_id == user_id,
            )
            .limit(1)
        )

    def list_by_report_id(self, report_id: int, *, user_id: int) -> list[TailoredResumeDraftRecord]:
        return list(
            self.db.scalars(
                select(TailoredResumeDraftRecord).where(
                    TailoredResumeDraftRecord.report_id == report_id,
                    TailoredResumeDraftRecord.user_id == user_id,
                )
            )
        )

    def add_or_get_by_application(
        self, record: TailoredResumeDraftRecord
    ) -> TailoredResumeDraftRecord:
        application_id = record.application_id
        user_id = record.user_id
        try:
            with self.db.begin_nested():
                self.db.add(record)
                self.db.flush()
        except IntegrityError:
            existing = self.get_by_application_id(application_id, user_id=user_id)
            if existing:
                return existing
            raise
        self.db.commit()
        self.db.refresh(record)
        return record

    def save(self, record: TailoredResumeDraftRecord) -> TailoredResumeDraftRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def delete(self, record: TailoredResumeDraftRecord) -> None:
        self.db.delete(record)
        self.db.flush()

    def delete_by_application_id(self, application_id: int, *, user_id: int) -> bool:
        record = self.get_by_application_id(application_id, user_id=user_id)
        if not record:
            return False
        self.delete(record)
        return True

    def delete_by_report_id(self, report_id: int, *, user_id: int) -> int:
        records = self.list_by_report_id(report_id, user_id=user_id)
        for record in records:
            self.db.delete(record)
        if records:
            self.db.flush()
        return len(records)
