from sqlalchemy import func, select, text

from app.db.models import UserRecord
from app.repositories.users import UserRepository
from app.services.identity_service import get_or_create_user


def test_get_or_create_user_persists_a_new_identity(client):
    session_factory = client.app.state.session_factory

    with session_factory() as db:
        current_user = get_or_create_user(
            db,
            external_id="new-identity",
            email="new@example.com",
            display_name="New User",
            initial_plan="pro",
            initial_subscription_status="active",
        )

        assert current_user.external_id == "new-identity"
        assert current_user.plan == "pro"
        assert current_user.subscription_status == "active"
        assert (
            db.scalar(
                select(func.count())
                .select_from(UserRecord)
                .where(UserRecord.external_id == "new-identity")
            )
            == 1
        )


def test_get_or_create_user_recovers_from_a_unique_insert_race(client, monkeypatch):
    session_factory = client.app.state.session_factory
    with session_factory() as seed_db:
        existing = UserRecord(
            external_id="racing-identity",
            email="old@example.com",
            display_name="Existing User",
            plan="premium",
            subscription_status="active",
        )
        seed_db.add(existing)
        seed_db.commit()
        seed_db.refresh(existing)
        existing_id = existing.id

    original_get = UserRepository.get_by_external_id
    lookup_count = 0

    def stale_first_lookup(self: UserRepository, external_id: str) -> UserRecord | None:
        nonlocal lookup_count
        lookup_count += 1
        if lookup_count == 1:
            return None
        return original_get(self, external_id)

    monkeypatch.setattr(UserRepository, "get_by_external_id", stale_first_lookup)

    with session_factory() as db:
        current_user = get_or_create_user(
            db,
            external_id="racing-identity",
            email="fresh@example.com",
            display_name="Fresh Profile",
            initial_plan="free",
            initial_subscription_status="inactive",
        )

        assert current_user.id == existing_id
        assert current_user.email == "fresh@example.com"
        assert current_user.display_name == "Fresh Profile"
        assert current_user.plan == "premium"
        assert current_user.subscription_status == "active"
        assert (
            db.scalar(
                select(func.count())
                .select_from(UserRecord)
                .where(UserRecord.external_id == "racing-identity")
            )
            == 1
        )
        assert db.scalar(text("SELECT 1")) == 1
