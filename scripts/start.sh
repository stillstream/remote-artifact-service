#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${ARTIFACT_SERVICE_CONFIG:-$ROOT/config/config.json}"
RUN_DIR="${XDG_RUNTIME_DIR:-$HOME/.local/run}/remote-artifact-service"
mkdir -p "$RUN_DIR"
PID_FILE="$RUN_DIR/service.pid"; LOG_FILE="$RUN_DIR/service.log"
[[ -x "$ROOT/.venv/bin/python" ]] || { echo 'Run scripts/install.sh first' >&2; exit 1; }
[[ -f "$CONFIG" ]] || { echo "Missing config: $CONFIG" >&2; exit 1; }
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then echo "Already running PID $(cat "$PID_FILE")"; exit 0; fi
cd "$ROOT"
nohup "$ROOT/.venv/bin/python" -m artifact_service --config "$CONFIG" >>"$LOG_FILE" 2>&1 </dev/null &
echo $! > "$PID_FILE"; sleep 1
if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then cat "$LOG_FILE"; rm -f "$PID_FILE"; exit 1; fi
echo "Started PID $(cat "$PID_FILE"); log: $LOG_FILE"
