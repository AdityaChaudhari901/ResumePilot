#!/usr/bin/env bash
set -euo pipefail

CONFIRM=false
DRY_RUN=false

case "${1:-}" in
  --yes)
    CONFIRM=true
    ;;
  --dry-run | "")
    DRY_RUN=true
    ;;
  -h | --help)
    cat <<'EOF'
Usage:
  ./Ai\ services/openclaw/scripts/repair_cli_device_pairing.sh --dry-run
  ./Ai\ services/openclaw/scripts/repair_cli_device_pairing.sh --yes

Repairs the local OpenClaw CLI operator device after a scope-upgrade loop by
adding operator.write and operator.pairing to the already paired local CLI
device. Creates timestamped backups and never prints the stored device token.
EOF
    exit 0
    ;;
  *)
    echo "Unknown option: ${1:-}" >&2
    echo "Use --dry-run or --yes." >&2
    exit 2
    ;;
esac

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required to repair OpenClaw device pairing." >&2
  exit 1
fi

DEVICES_DIR="${OPENCLAW_DEVICES_DIR:-$HOME/.openclaw/devices}"
PAIRED_FILE="$DEVICES_DIR/paired.json"
PENDING_FILE="$DEVICES_DIR/pending.json"

if [ ! -f "$PAIRED_FILE" ]; then
  echo "OpenClaw paired device file not found: $PAIRED_FILE" >&2
  exit 1
fi

if [ ! -f "$PENDING_FILE" ]; then
  echo '{}' >"$PENDING_FILE"
  chmod 600 "$PENDING_FILE"
fi

DEVICE_ID="$(jq -r 'to_entries[] | select(.value.clientId == "cli" and .value.role == "operator") | .key' "$PAIRED_FILE" | head -n 1)"

if [ -z "$DEVICE_ID" ]; then
  echo "No paired OpenClaw CLI operator device found." >&2
  exit 1
fi

CURRENT_SCOPES="$(jq -r --arg id "$DEVICE_ID" '.[$id].approvedScopes // [] | join(",")' "$PAIRED_FILE")"
PENDING_COUNT="$(jq --arg id "$DEVICE_ID" '[to_entries[] | select(.value.deviceId == $id)] | length' "$PENDING_FILE")"

echo "OpenClaw CLI device: ${DEVICE_ID:0:12}..."
echo "Approved scopes: ${CURRENT_SCOPES:-none}"
echo "Pending requests for this device: $PENDING_COUNT"

if jq -e --arg id "$DEVICE_ID" '((.[$id].approvedScopes // []) | index("operator.write")) and ((.[$id].approvedScopes // []) | index("operator.pairing"))' "$PAIRED_FILE" >/dev/null; then
  echo "Device already has operator.write and operator.pairing."
  exit 0
fi

if [ "$DRY_RUN" = true ]; then
  echo "Dry run only. Re-run with --yes to repair the local pairing state."
  exit 0
fi

if [ "$CONFIRM" != true ]; then
  echo "Refusing to modify local OpenClaw pairing state without --yes." >&2
  exit 2
fi

BACKUP_SUFFIX="$(date +%Y%m%d%H%M%S)"
cp "$PAIRED_FILE" "$PAIRED_FILE.bak-$BACKUP_SUFFIX"
cp "$PENDING_FILE" "$PENDING_FILE.bak-$BACKUP_SUFFIX"

TMP_PAIRED="$(mktemp)"
TMP_PENDING="$(mktemp)"

jq --arg id "$DEVICE_ID" '
  .[$id] |= (
    .scopes = (((.scopes // []) + ["operator.write", "operator.pairing"]) | unique)
    | .approvedScopes = (((.approvedScopes // []) + ["operator.write", "operator.pairing"]) | unique)
    | .tokens.operator.scopes = (((.tokens.operator.scopes // []) + ["operator.write", "operator.pairing"]) | unique)
  )
' "$PAIRED_FILE" >"$TMP_PAIRED"

jq --arg id "$DEVICE_ID" 'with_entries(select(.value.deviceId != $id))' "$PENDING_FILE" >"$TMP_PENDING"

cat "$TMP_PAIRED" >"$PAIRED_FILE"
cat "$TMP_PENDING" >"$PENDING_FILE"
rm -f "$TMP_PAIRED" "$TMP_PENDING"
chmod 600 "$PAIRED_FILE" "$PENDING_FILE"

echo "Repair complete. Backups created with suffix $BACKUP_SUFFIX."
echo "Restart the OpenClaw Gateway before retrying openclaw agent."
