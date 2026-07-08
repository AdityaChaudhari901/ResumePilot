from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "workspace"
    / "skills"
    / "job"
    / "scripts"
    / "resumepilot_job.py"
)

spec = importlib.util.spec_from_file_location("resumepilot_job", SCRIPT_PATH)
resumepilot_job = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules["resumepilot_job"] = resumepilot_job
spec.loader.exec_module(resumepilot_job)


class ResumePilotJobHelperTests(unittest.TestCase):
    def test_normalize_command_args_keeps_url(self) -> None:
        self.assertEqual(
            resumepilot_job.normalize_command_args(" https://example.com/job/123 "),
            "https://example.com/job/123",
        )

    def test_normalize_command_args_supports_paste_space_alias(self) -> None:
        self.assertEqual(
            resumepilot_job.normalize_command_args("paste Role: Backend Engineer"),
            "paste:Role: Backend Engineer",
        )

    def test_normalize_command_args_strips_job_prefix(self) -> None:
        self.assertEqual(
            resumepilot_job.normalize_command_args("/job paste Role: Backend Engineer"),
            "paste:Role: Backend Engineer",
        )

    def test_normalize_command_args_strips_skill_job_prefix(self) -> None:
        self.assertEqual(
            resumepilot_job.normalize_command_args(
                "/skill job paste:Role: Backend Engineer"
            ),
            "paste:Role: Backend Engineer",
        )

    def test_build_payload_uses_openclaw_identity(self) -> None:
        config = resumepilot_job.ResumePilotConfig(
            api_base_url="http://127.0.0.1:8002",
            api_token="secret",
            sender_id="telegram:12345",
            session_id="telegram:slash:12345",
        )

        payload = resumepilot_job.build_payload(config, "paste:Role: Backend Engineer")

        self.assertEqual(
            payload,
            {
                "command": "job",
                "args": "paste:Role: Backend Engineer",
                "sender": "telegram:12345",
                "session_id": "telegram:slash:12345",
            },
        )

    def test_config_from_env_requires_token(self) -> None:
        env = {key: value for key, value in os.environ.items() if key != "JOBCOPILOT_API_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                resumepilot_job.ResumePilotClientError, "JOBCOPILOT_API_TOKEN"
            ):
                resumepilot_job.config_from_env()


if __name__ == "__main__":
    unittest.main()
