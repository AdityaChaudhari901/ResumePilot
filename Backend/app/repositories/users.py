from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import UserRecord


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: int) -> UserRecord | None:
        return self.db.get(UserRecord, user_id)

    def get_by_external_id(self, external_id: str) -> UserRecord | None:
        return self.db.scalar(
            select(UserRecord).where(UserRecord.external_id == external_id).limit(1)
        )

    def add(self, record: UserRecord) -> UserRecord:
        self.db.add(record)
        self.db.flush()
        return record

    def save(self, record: UserRecord) -> UserRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
