#!/usr/bin/env bash
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
VENV_DIR="${VENV_DIR:-.venv}"
INSTALL_EXTRAS="${INSTALL_EXTRAS:-dev,ai}"
CONSTRAINTS_FILE="${CONSTRAINTS_FILE:-requirements/py312-dev-ai.constraints.txt}"
RECREATE=0

usage() {
  cat <<'USAGE'
Usage: scripts/bootstrap_py312.sh [--recreate]

Creates or updates the backend virtual environment with Python 3.12 and the
pinned ResumePilot dependency constraints.

Environment overrides:
  PYTHON_BIN        Python executable to use. Default: python3.12
  VENV_DIR          Virtualenv path relative to Backend/. Default: .venv
  INSTALL_EXTRAS    Editable install extras. Default: dev,ai
  CONSTRAINTS_FILE  Constraints file. Default: requirements/py312-dev-ai.constraints.txt

Examples:
  scripts/bootstrap_py312.sh
  scripts/bootstrap_py312.sh --recreate
  VENV_DIR=.local/venvs/py312 scripts/bootstrap_py312.sh
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --recreate)
      RECREATE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$BACKEND_DIR"

if [[ ! -f "$CONSTRAINTS_FILE" ]]; then
  echo "Constraints file not found: $CONSTRAINTS_FILE" >&2
  exit 1
fi

if [[ "$RECREATE" -eq 1 && -d "$VENV_DIR" ]]; then
  rm -rf "$VENV_DIR"
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_VERSION="$("$VENV_DIR/bin/python" - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"

if [[ "$VENV_VERSION" != "3.12" ]]; then
  echo "Virtualenv at $VENV_DIR uses Python $VENV_VERSION, expected Python 3.12." >&2
  echo "Run with --recreate or set VENV_DIR to a Python 3.12 environment." >&2
  exit 1
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -e ".[${INSTALL_EXTRAS}]" -c "$CONSTRAINTS_FILE"
"$VENV_DIR/bin/python" -m pip check
"$VENV_DIR/bin/python" --version

echo "Backend environment ready at $BACKEND_DIR/$VENV_DIR"
