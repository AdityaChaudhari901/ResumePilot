#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_SENDER_ID = "openclaw:local"
DEFAULT_SESSION_ID = "openclaw:resume-pilot"


@dataclass(frozen=True)
class ResumePilotConfig:
    api_base_url: str
    api_token: str
    sender_id: str
    session_id: str


class ResumePilotClientError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Call ResumePilot /chat/openclaw for the OpenClaw /job skill."
    )
    parser.add_argument("args", nargs="*", help="Job URL or pasted job description.")
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read job input from stdin instead of positional arguments.",
    )
    parsed = parser.parse_args()

    raw_args = sys.stdin.read() if parsed.stdin else " ".join(parsed.args)
    command_args = normalize_command_args(raw_args)
    if not command_args:
        print(
            "Usage: /job <url> or /job paste:<job description>",
            file=sys.stderr,
        )
        return 2

    try:
        config = config_from_env()
        markdown = call_resumepilot(config, command_args)
    except ResumePilotClientError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(markdown)
    return 0


def config_from_env() -> ResumePilotConfig:
    token = os.environ.get("JOBCOPILOT_API_TOKEN", "").strip()
    if not token:
        raise ResumePilotClientError("JOBCOPILOT_API_TOKEN is required.")

    return ResumePilotConfig(
        api_base_url=os.environ.get("RESUMEPILOT_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/"),
        api_token=token,
        sender_id=os.environ.get("OPENCLAW_SENDER_ID", DEFAULT_SENDER_ID).strip()
        or DEFAULT_SENDER_ID,
        session_id=os.environ.get("OPENCLAW_SESSION_ID", DEFAULT_SESSION_ID).strip()
        or DEFAULT_SESSION_ID,
    )


def normalize_command_args(raw_args: str) -> str:
    cleaned = raw_args.strip()
    if cleaned.lower().startswith("paste "):
        return "paste:" + cleaned[6:].strip()
    return cleaned


def build_payload(config: ResumePilotConfig, command_args: str) -> dict[str, str]:
    return {
        "command": "job",
        "args": command_args,
        "sender": config.sender_id,
        "session_id": config.session_id,
    }


def call_resumepilot(config: ResumePilotConfig, command_args: str) -> str:
    payload = json.dumps(build_payload(config, command_args)).encode("utf-8")
    request = urllib.request.Request(
        f"{config.api_base_url}/chat/openclaw",
        data=payload,
        headers={
            "Authorization": f"Bearer {config.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ResumePilotClientError(format_http_error(exc)) from exc
    except urllib.error.URLError as exc:
        raise ResumePilotClientError(
            f"ResumePilot API is unreachable at {config.api_base_url}: {exc.reason}"
        ) from exc
    except TimeoutError as exc:
        raise ResumePilotClientError(
            f"ResumePilot API timed out at {config.api_base_url}."
        ) from exc
    except json.JSONDecodeError as exc:
        raise ResumePilotClientError("ResumePilot API returned invalid JSON.") from exc

    markdown = body.get("markdown")
    if not markdown:
        raise ResumePilotClientError(
            f"ResumePilot API completed without a Markdown report: {body!r}"
        )
    return markdown


def format_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        body = {}
    detail = body.get("detail") if isinstance(body, dict) else None
    message = detail or exc.reason or "OpenClaw request failed"
    return f"ResumePilot API returned {exc.code}: {message}"


if __name__ == "__main__":
    raise SystemExit(main())
