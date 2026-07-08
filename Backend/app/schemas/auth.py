from app.schemas.common import StrictBaseModel


class CurrentUser(StrictBaseModel):
    id: int
    external_id: str
    email: str | None = None
    display_name: str | None = None
    plan: str
    subscription_status: str
