from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import UsageEventRecord


class UsageEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, record: UsageEventRecord) -> UsageEventRecord:
        self.db.add(record)
        self.db.flush()
        return record

    def quantity_sum(
        self,
        *,
        user_id: int,
        event_types: set[str],
        start_at: datetime,
        end_at: datetime,
    ) -> int:
        value = self.db.scalar(
            select(func.coalesce(func.sum(UsageEventRecord.quantity), 0)).where(
                UsageEventRecord.user_id == user_id,
                UsageEventRecord.event_type.in_(event_types),
                UsageEventRecord.created_at >= start_at,
                UsageEventRecord.created_at < end_at,
            )
        )
        return int(value or 0)

    def cost_sum(
        self,
        *,
        user_id: int,
        start_at: datetime,
        end_at: datetime,
    ) -> float:
        value = self.db.scalar(
            select(func.coalesce(func.sum(UsageEventRecord.cost_estimate_usd), 0.0)).where(
                UsageEventRecord.user_id == user_id,
                UsageEventRecord.created_at >= start_at,
                UsageEventRecord.created_at < end_at,
            )
        )
        return float(value or 0.0)
