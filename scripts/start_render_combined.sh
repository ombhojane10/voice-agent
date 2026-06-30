#!/usr/bin/env bash
set -euo pipefail

uv run --no-sync voice-agent-worker start &
worker_pid=$!

cleanup() {
  kill "$worker_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

uv run --no-sync voice-agent-api
