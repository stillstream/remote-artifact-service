#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="${XDG_RUNTIME_DIR:-$HOME/.local/run}/remote-artifact-service"
PID_FILE="$RUN_DIR/service.pid"
[[ -f "$PID_FILE" ]] || { echo 'Not running'; exit 0; }
PID="$(cat "$PID_FILE")"; [[ "$PID" =~ ^[0-9]+$ ]] || { echo 'Invalid PID file' >&2; exit 1; }
if kill -0 "$PID" 2>/dev/null; then
  CMD="$(tr '\0' ' ' <"/proc/$PID/cmdline" 2>/dev/null || true)"
  [[ "$CMD" == *'artifact_service'* ]] || { echo "PID $PID is not artifact_service; refusing" >&2; exit 1; }
  kill -TERM "$PID"
fi
rm -f "$PID_FILE"; echo "Stopped PID $PID"
