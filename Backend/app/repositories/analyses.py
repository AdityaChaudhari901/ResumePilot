from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

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

    def get_for_update(self, analysis_id: int, *, user_id: int) -> AnalysisRecord | None:
        return self.db.scalar(
            select(AnalysisRecord)
            .where(AnalysisRecord.id == analysis_id, AnalysisRecord.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
            .limit(1)
        )

    def get_by_workflow_job_id(
        self,
        workflow_job_id: str,
        *,
        user_id: int,
    ) -> AnalysisRecord | None:
        return self.db.scalar(
            select(AnalysisRecord)
            .where(
                AnalysisRecord.workflow_job_id == workflow_job_id,
                AnalysisRecord.user_id == user_id,
            )
            .limit(1)
        )

    def get_by_workflow_job_id_for_update(
        self,
        workflow_job_id: str,
        *,
        user_id: int,
    ) -> AnalysisRecord | None:
        return self.db.scalar(
            select(AnalysisRecord)
            .where(
                AnalysisRecord.workflow_job_id == workflow_job_id,
                AnalysisRecord.user_id == user_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
            .limit(1)
        )

    def list_recent(self, *, user_id: int, limit: int = 20) -> list[AnalysisRecord]:
        return list(
            self.db.scalars(
                select(AnalysisRecord)
                .options(
                    selectinload(AnalysisRecord.resume),
                    selectinload(AnalysisRecord.job),
                )
                .where(AnalysisRecord.user_id == user_id)
                .order_by(AnalysisRecord.created_at.desc(), AnalysisRecord.id.desc())
                .limit(limit)
            )
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
