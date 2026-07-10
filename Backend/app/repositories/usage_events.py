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

    def get_by_reservation_key(self, reservation_key: str) -> UsageEventRecord | None:
        return self.db.scalar(
            select(UsageEventRecord)
            .where(UsageEventRecord.reservation_key == reservation_key)
            .limit(1)
        )

    def quantity_sum(
        self,
        *,
        user_id: int,
        event_types: set[str],
        start_at: datetime,
        end_at: datetime,
        states: set[str] | None = None,
        reserved_after: datetime | None = None,
    ) -> int:
        query = select(func.coalesce(func.sum(UsageEventRecord.quantity), 0)).where(
            UsageEventRecord.user_id == user_id,
            UsageEventRecord.event_type.in_(event_types),
            UsageEventRecord.created_at >= start_at,
            UsageEventRecord.created_at < end_at,
        )
        if states:
            query = query.where(UsageEventRecord.state.in_(states))
        if reserved_after is not None:
            query = query.where(
                (UsageEventRecord.state != "reserved")
                | (UsageEventRecord.reserved_at >= reserved_after)
            )
        value = self.db.scalar(query)
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
                UsageEventRecord.state == "consumed",
                UsageEventRecord.created_at >= start_at,
                UsageEventRecord.created_at < end_at,
            )
        )
        return float(value or 0.0)
