from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import time
from types import FrameType
from uuid import uuid4

from app.core.config import Settings
from app.core.logging import configure_logging
from app.core.production import validate_production_settings
from app.db.session import create_database_engine, create_session_factory
from app.services.langgraph_checkpointer import (
    close_workflow_checkpointers,
    reconcile_terminal_workflow_checkpoints,
)
from app.services.readiness_service import check_application_readiness
from app.services.workflow_job_service import execute_next_workflow_job

LOGGER = logging.getLogger("resumepilot.worker")


class ShutdownSignal:
    def __init__(self) -> None:
        self.requested = False

    def request(self, _signum: int, _frame: FrameType | None) -> None:
        self.requested = True


def run_worker(*, once: bool = False) -> int:
    settings = Settings()
    validate_production_settings(settings)
    configure_logging(settings.debug)
    engine = create_database_engine(settings)
    try:
        ensure_worker_readiness(engine, settings)
    except Exception:
        engine.dispose()
        raise
    session_factory = create_session_factory(engine)
    worker_id = f"{socket.gethostname()}-{os.getpid()}-{str(uuid4())[:8]}"
    shutdown = ShutdownSignal()
    signal.signal(signal.SIGTERM, shutdown.request)
    signal.signal(signal.SIGINT, shutdown.request)
    LOGGER.info("workflow worker started", extra={"worker_id": worker_id})
    reconciled = reconcile_terminal_workflow_checkpoints(settings)
    LOGGER.info(
        "workflow checkpoints reconciled",
        extra={"worker_id": worker_id, "checkpoint_threads_deleted": reconciled},
    )
    last_checkpoint_reconcile = time.monotonic()

    try:
        while not shutdown.requested:
            if (
                time.monotonic() - last_checkpoint_reconcile
                >= settings.workflow_checkpoint_reconcile_seconds
            ):
                try:
                    reconciled = reconcile_terminal_workflow_checkpoints(settings)
                    LOGGER.info(
                        "workflow checkpoints reconciled",
                        extra={
                            "worker_id": worker_id,
                            "checkpoint_threads_deleted": reconciled,
                        },
                    )
                except Exception:
                    LOGGER.exception(
                        "workflow checkpoint reconciliation failed",
                        extra={"worker_id": worker_id},
                    )
                last_checkpoint_reconcile = time.monotonic()
            with session_factory() as db:
                record = execute_next_workflow_job(db, settings=settings, worker_id=worker_id)
            if record is not None:
                LOGGER.info(
                    "workflow job settled",
                    extra={
                        "worker_id": worker_id,
                        "workflow_job_id": record.id,
                        "workflow_job_status": record.status,
                        "workflow_job_kind": record.kind,
                    },
                )
            if once:
                return 0
            if record is None:
                time.sleep(settings.workflow_worker_poll_seconds)
    finally:
        close_workflow_checkpointers()
        engine.dispose()

    LOGGER.info("workflow worker stopped", extra={"worker_id": worker_id})
    return 0


def ensure_worker_readiness(engine, settings: Settings) -> None:
    readiness = check_application_readiness(engine, settings)
    if readiness.status == "ok":
        return
    failed_checks = "; ".join(
        f"{check.name}: {check.detail}" for check in readiness.checks if check.status == "failed"
    )
    raise RuntimeError(f"Workflow worker readiness failed: {failed_checks}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ResumePilot durable workflow worker")
    parser.add_argument("--once", action="store_true", help="Claim at most one available job")
    args = parser.parse_args()
    raise SystemExit(run_worker(once=args.once))


if __name__ == "__main__":
    main()
