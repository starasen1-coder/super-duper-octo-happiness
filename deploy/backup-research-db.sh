#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${AGENT_REACH_DB:-/var/lib/agent-reach/research.sqlite3}"
BACKUP_DIR="${AGENT_REACH_BACKUP_DIR:-/var/backups/agent-reach}"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

if [[ ! -f "$DB_PATH" ]]; then
  echo "Database not found: $DB_PATH" >&2
  exit 1
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$BACKUP_DIR/research-$STAMP.sqlite3"
python3 - "$DB_PATH" "$DEST" <<'PY'
import sqlite3
import sys

source, destination = sys.argv[1:3]
with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
    src.backup(dst)
PY
chmod 600 "$DEST"

KEEP="${AGENT_REACH_BACKUP_KEEP:-14}"
if ! [[ "$KEEP" =~ ^[1-9][0-9]*$ ]]; then
  echo "AGENT_REACH_BACKUP_KEEP must be a positive integer" >&2
  exit 1
fi
mapfile -t OLD_BACKUPS < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'research-*.sqlite3' -printf '%f\n' | sort -r | tail -n +"$((KEEP + 1))")
for name in "${OLD_BACKUPS[@]}"; do
  rm -f -- "$BACKUP_DIR/$name"
done

echo "$DEST"
