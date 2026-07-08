from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "register_vertex_model.py"

spec = importlib.util.spec_from_file_location("register_vertex_model", SCRIPT_PATH)
register_vertex_model = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules["register_vertex_model"] = register_vertex_model
spec.loader.exec_module(register_vertex_model)


class RegisterVertexModelTests(unittest.TestCase):
    def test_registers_global_and_agent_provider_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            global_config = root / "openclaw.json"
            agent_models = root / "agents" / "main" / "agent" / "models.json"
            global_config.write_text(
                json.dumps(
                    {
                        "gateway": {"mode": "local"},
                        "agents": {
                            "defaults": {
                                "models": {"google-vertex/gemini-2.5-flash": {}}
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            agent_models.parent.mkdir(parents=True)
            agent_models.write_text(json.dumps({"providers": {}}), encoding="utf-8")

            env = {
                **os.environ,
                "OPENCLAW_CONFIG_FILE": str(global_config),
                "OPENCLAW_AGENT_MODELS_FILE": str(agent_models),
                "VERTEX_PROJECT_ID": "demo-project",
                "VERTEX_REGION": "global",
                "LLM_MODEL": "gemini-3.5-flash",
                "OPENCLAW_MODEL_REFERENCE": "google-vertex/gemini-3.5-flash",
            }

            with patch.dict(os.environ, env, clear=True):
                with redirect_stdout(StringIO()):
                    exit_code = register_vertex_model.main()

            self.assertEqual(exit_code, 0)
            global_body = json.loads(global_config.read_text(encoding="utf-8"))
            agent_body = json.loads(agent_models.read_text(encoding="utf-8"))

            provider = global_body["models"]["providers"]["google-vertex"]
            self.assertEqual(provider["api"], "google-vertex")
            self.assertEqual(provider["params"]["project"], "demo-project")
            self.assertEqual(provider["params"]["location"], "global")
            self.assertIn(
                {"id": "gemini-3.5-flash", "name": "Gemini 3.5 Flash", "api": "google-vertex", "input": ["text", "image"], "contextWindow": 1048576, "contextTokens": 1048576, "maxTokens": 65536},
                provider["models"],
            )
            self.assertEqual(
                global_body["agents"]["defaults"]["model"]["primary"],
                "google-vertex/gemini-3.5-flash",
            )
            self.assertIn(
                "google-vertex/gemini-3.5-flash",
                global_body["agents"]["defaults"]["models"],
            )
            self.assertIn(
                "google-vertex",
                agent_body["providers"],
            )


if __name__ == "__main__":
    unittest.main()
