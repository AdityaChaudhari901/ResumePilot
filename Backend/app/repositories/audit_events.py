from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEventRecord


class AuditEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        *,
        user_id: int,
        limit: int,
        event_type: str | None = None,
    ) -> list[AuditEventRecord]:
        statement = (
            select(AuditEventRecord)
            .where(AuditEventRecord.user_id == user_id)
            .order_by(AuditEventRecord.created_at.desc())
        )
        if event_type:
            statement = statement.where(AuditEventRecord.event_type == event_type)
        return list(self.db.scalars(statement.limit(limit)))

    def get_for_analysis(
        self,
        *,
        user_id: int,
        event_type: str,
        analysis_id: int,
    ) -> AuditEventRecord | None:
        return self.db.scalar(
            select(AuditEventRecord)
            .where(
                AuditEventRecord.user_id == user_id,
                AuditEventRecord.event_type == event_type,
                AuditEventRecord.payload_json["analysis_id"].as_integer() == analysis_id,
            )
            .limit(1)
        )

    def add(self, record: AuditEventRecord) -> AuditEventRecord:
        self.db.add(record)
        self.db.flush()
        return record
