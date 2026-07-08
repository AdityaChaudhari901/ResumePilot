from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime

AUTH_TIMESTAMP_HEADER = "x-resumepilot-auth-timestamp"
AUTH_SIGNATURE_HEADER = "x-resumepilot-auth-signature"


def sign_identity(
    *,
    secret: str,
    external_id: str,
    email: str | None,
    display_name: str | None,
    timestamp: str,
) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        _identity_payload(
            external_id=external_id,
            email=email,
            display_name=display_name,
            timestamp=timestamp,
        ).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_identity_signature(
    *,
    secret: str,
    external_id: str,
    email: str | None,
    display_name: str | None,
    timestamp: str | None,
    signature: str | None,
    max_age_seconds: int,
    now: datetime | None = None,
) -> bool:
    if not timestamp or not signature:
        return False
    try:
        issued_at = int(timestamp)
    except ValueError:
        return False

    now_seconds = int((now or datetime.now(UTC)).timestamp())
    if abs(now_seconds - issued_at) > max_age_seconds:
        return False

    expected_signature = sign_identity(
        secret=secret,
        external_id=external_id,
        email=email,
        display_name=display_name,
        timestamp=timestamp,
    )
    return hmac.compare_digest(expected_signature, signature)


def _identity_payload(
    *,
    external_id: str,
    email: str | None,
    display_name: str | None,
    timestamp: str,
) -> str:
    return "\n".join([external_id, email or "", display_name or "", timestamp])
