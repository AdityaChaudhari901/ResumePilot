from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApplicationRecord


class ApplicationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, application_id: int, *, user_id: int) -> ApplicationRecord | None:
        return self.db.scalar(
            select(ApplicationRecord)
            .where(ApplicationRecord.id == application_id, ApplicationRecord.user_id == user_id)
            .limit(1)
        )

    def get_for_update(self, application_id: int, *, user_id: int) -> ApplicationRecord | None:
        return self.db.scalar(
            select(ApplicationRecord)
            .where(ApplicationRecord.id == application_id, ApplicationRecord.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
            .limit(1)
        )

    def get_by_report_id(self, report_id: int, *, user_id: int) -> ApplicationRecord | None:
        return self.db.scalar(
            select(ApplicationRecord)
            .where(ApplicationRecord.report_id == report_id, ApplicationRecord.user_id == user_id)
            .limit(1)
        )

    def get_by_report_id_for_update(
        self, report_id: int, *, user_id: int
    ) -> ApplicationRecord | None:
        return self.db.scalar(
            select(ApplicationRecord)
            .where(ApplicationRecord.report_id == report_id, ApplicationRecord.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
            .limit(1)
        )

    def list_recent(self, *, user_id: int, limit: int = 20) -> list[ApplicationRecord]:
        return list(
            self.db.scalars(
                select(ApplicationRecord)
                .where(ApplicationRecord.user_id == user_id)
                .order_by(ApplicationRecord.updated_at.desc(), ApplicationRecord.id.desc())
                .limit(limit)
            )
        )

    def add(self, record: ApplicationRecord) -> ApplicationRecord:
        self.db.add(record)
        self.db.flush()
        return record

    def save(self, record: ApplicationRecord) -> ApplicationRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
