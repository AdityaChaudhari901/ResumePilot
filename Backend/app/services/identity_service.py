from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import UserRecord
from app.repositories.users import UserRepository
from app.schemas.auth import CurrentUser


def get_or_create_user(
    db: Session,
    *,
    external_id: str,
    email: str | None = None,
    display_name: str | None = None,
    initial_plan: str = "free",
    initial_subscription_status: str = "inactive",
) -> CurrentUser:
    repository = UserRepository(db)
    record = repository.get_by_external_id(external_id)
    if record is None:
        record = _create_user_or_reselect(
            db,
            repository,
            external_id=external_id,
            email=email,
            display_name=display_name,
            initial_plan=initial_plan,
            initial_subscription_status=initial_subscription_status,
        )

    changed = False
    if email and email != record.email:
        record.email = email
        changed = True
    if display_name and display_name != record.display_name:
        record.display_name = display_name
        changed = True
    if changed:
        repository.save(record)
    return _current_user_from_record(record)


def _create_user_or_reselect(
    db: Session,
    repository: UserRepository,
    *,
    external_id: str,
    email: str | None,
    display_name: str | None,
    initial_plan: str,
    initial_subscription_status: str,
) -> UserRecord:
    """Insert a user without invalidating the request transaction on an auth race."""

    record = UserRecord(
        external_id=external_id,
        email=email,
        display_name=display_name,
        plan=initial_plan,
        subscription_status=initial_subscription_status,
    )
    try:
        with db.begin_nested():
            repository.add(record)
    except IntegrityError:
        # Another request may have inserted the same external identity after our
        # initial lookup. The savepoint rollback keeps the outer session usable.
        concurrent_record = repository.get_by_external_id(external_id)
        if concurrent_record is None:
            raise
        return concurrent_record

    db.commit()
    db.refresh(record)
    return record


def _current_user_from_record(record: UserRecord) -> CurrentUser:
    return CurrentUser(
        id=record.id,
        external_id=record.external_id,
        email=record.email,
        display_name=record.display_name,
        plan=record.plan,
        subscription_status=record.subscription_status,
    )
