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
) -> CurrentUser:
    repository = UserRepository(db)
    record = repository.get_by_external_id(external_id)
    if record is None:
        record = UserRecord(
            external_id=external_id,
            email=email,
            display_name=display_name,
            plan="free",
            subscription_status="inactive",
        )
        repository.save(record)
        return _current_user_from_record(record)

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


def _current_user_from_record(record: UserRecord) -> CurrentUser:
    return CurrentUser(
        id=record.id,
        external_id=record.external_id,
        email=record.email,
        display_name=record.display_name,
        plan=record.plan,
        subscription_status=record.subscription_status,
    )
