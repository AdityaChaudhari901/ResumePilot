from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from httpx import Response


def analysis_headers(
    headers: dict[str, str] | None = None,
    *,
    idempotency_key: str | None = None,
) -> dict[str, str]:
    return {
        **(headers or {}),
        "Idempotency-Key": idempotency_key or f"test-analysis-{uuid4()}",
    }


def submit_analysis(
    client: TestClient,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    idempotency_key: str | None = None,
) -> tuple[Response, dict[str, Any] | None]:
    response = client.post(
        "/jobs/analyze",
        json=payload,
        headers=analysis_headers(headers, idempotency_key=idempotency_key),
    )
    body = (
        response.json()
        if response.headers.get("content-type", "").startswith("application/json")
        else None
    )
    return response, body


def successful_analysis(
    client: TestClient,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    response, operation = submit_analysis(
        client,
        payload,
        headers=headers,
        idempotency_key=idempotency_key,
    )
    assert response.status_code == 202
    assert operation is not None
    assert operation["status"] == "succeeded", operation
    assert operation["result"] is not None
    return operation["result"]
