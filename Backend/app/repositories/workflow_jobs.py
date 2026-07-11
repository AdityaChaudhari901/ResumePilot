from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import WorkflowJobRecord
from app.schemas.operation import ACTIVE_WORKFLOW_JOB_STATUSES, WorkflowJobStatus

SCORE_V2_WORKER_PREFIX = "score-v2:"


class WorkflowJobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, job_id: str, *, user_id: int) -> WorkflowJobRecord | None:
        return self.db.scalar(
            select(WorkflowJobRecord)
            .where(WorkflowJobRecord.id == job_id, WorkflowJobRecord.user_id == user_id)
            .limit(1)
        )

    def get_for_update(self, job_id: str, *, user_id: int) -> WorkflowJobRecord | None:
        return self.db.scalar(
            select(WorkflowJobRecord)
            .where(WorkflowJobRecord.id == job_id, WorkflowJobRecord.user_id == user_id)
            .with_for_update()
            .limit(1)
        )

    def get_any(self, job_id: str) -> WorkflowJobRecord | None:
        return self.db.scalar(
            select(WorkflowJobRecord).where(WorkflowJobRecord.id == job_id).limit(1)
        )

    def get_any_for_update(self, job_id: str) -> WorkflowJobRecord | None:
        return self.db.scalar(
            select(WorkflowJobRecord)
            .where(WorkflowJobRecord.id == job_id)
            .with_for_update()
            .limit(1)
        )

    def get_by_idempotency_key(
        self,
        *,
        user_id: int,
        kind: str,
        idempotency_key_hash: str,
    ) -> WorkflowJobRecord | None:
        return self.db.scalar(
            select(WorkflowJobRecord)
            .where(
                WorkflowJobRecord.user_id == user_id,
                WorkflowJobRecord.kind == kind,
                WorkflowJobRecord.idempotency_key_hash == idempotency_key_hash,
            )
            .limit(1)
        )

    def list_recent(self, *, user_id: int, limit: int = 20) -> list[WorkflowJobRecord]:
        return list(
            self.db.scalars(
                select(WorkflowJobRecord)
                .where(WorkflowJobRecord.user_id == user_id)
                .order_by(WorkflowJobRecord.created_at.desc(), WorkflowJobRecord.id.desc())
                .limit(limit)
            )
        )

    def list_active(
        self,
        *,
        user_id: int,
        kind: str,
        application_id: int | None = None,
        limit: int = 1,
    ) -> list[WorkflowJobRecord]:
        statement = select(WorkflowJobRecord).where(
            WorkflowJobRecord.user_id == user_id,
            WorkflowJobRecord.kind == kind,
            WorkflowJobRecord.status.in_({status.value for status in ACTIVE_WORKFLOW_JOB_STATUSES}),
        )
        if application_id is not None:
            statement = statement.where(WorkflowJobRecord.application_id == application_id)
        return list(
            self.db.scalars(
                statement.order_by(
                    WorkflowJobRecord.created_at.desc(),
                    WorkflowJobRecord.id.desc(),
                ).limit(limit)
            )
        )

    def add(self, record: WorkflowJobRecord) -> WorkflowJobRecord:
        self.db.add(record)
        self.db.flush()
        return record

    def save(self, record: WorkflowJobRecord) -> WorkflowJobRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def claim_next(
        self,
        *,
        worker_id: str,
        lease_expires_at: datetime,
    ) -> WorkflowJobRecord | None:
        now = datetime.now(UTC)
        record = self.db.scalar(
            select(WorkflowJobRecord)
            .where(
                or_(
                    WorkflowJobRecord.status == WorkflowJobStatus.queued.value,
                    (
                        (WorkflowJobRecord.status == WorkflowJobStatus.retry_scheduled.value)
                        & (WorkflowJobRecord.available_at <= now)
                    ),
                    (
                        (WorkflowJobRecord.status == WorkflowJobStatus.running.value)
                        & (WorkflowJobRecord.lease_expires_at.is_not(None))
                        & (WorkflowJobRecord.lease_expires_at <= now)
                    ),
                    (
                        (WorkflowJobRecord.status == WorkflowJobStatus.cancel_requested.value)
                        & (WorkflowJobRecord.lease_expires_at.is_not(None))
                        & (WorkflowJobRecord.lease_expires_at <= now)
                    ),
                )
            )
            .order_by(
                WorkflowJobRecord.priority.desc(),
                WorkflowJobRecord.available_at.asc(),
                WorkflowJobRecord.created_at.asc(),
            )
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if record is None:
            return None
        record.status = WorkflowJobStatus.running.value
        record.stage = "starting"
        record.progress_percent = max(record.progress_percent, 5)
        record.attempt_count += 1
        record.lease_owner = _compatible_lease_owner(record, worker_id)
        record.lease_expires_at = lease_expires_at
        record.heartbeat_at = now
        record.started_at = record.started_at or now
        record.updated_at = now
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def claim_by_id(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_expires_at: datetime,
    ) -> WorkflowJobRecord | None:
        now = datetime.now(UTC)
        record = self.db.scalar(
            select(WorkflowJobRecord)
            .where(
                WorkflowJobRecord.id == job_id,
                WorkflowJobRecord.status.in_(
                    {
                        WorkflowJobStatus.queued.value,
                        WorkflowJobStatus.retry_scheduled.value,
                    }
                ),
                WorkflowJobRecord.available_at <= now,
            )
            .with_for_update()
            .limit(1)
        )
        if record is None:
            return None
        record.status = WorkflowJobStatus.running.value
        record.stage = "starting"
        record.progress_percent = max(record.progress_percent, 5)
        record.attempt_count += 1
        record.lease_owner = _compatible_lease_owner(record, worker_id)
        record.lease_expires_at = lease_expires_at
        record.heartbeat_at = now
        record.started_at = record.started_at or now
        record.updated_at = now
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record


def _compatible_lease_owner(record: WorkflowJobRecord, worker_id: str) -> str:
    if (
        record.kind == "analysis"
        and record.scoring_version == "evidence_v2"
        and not worker_id.startswith(SCORE_V2_WORKER_PREFIX)
    ):
        return f"{SCORE_V2_WORKER_PREFIX}{worker_id}"[:255]
    return worker_id[:255]
