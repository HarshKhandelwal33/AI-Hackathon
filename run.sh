#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if ! docker ps --filter name=^/serenedb$ --filter status=running --format '{{.Names}}' | grep -qx serenedb; then
  docker start serenedb >/dev/null
fi

"$ROOT/.venv/bin/python" "$ROOT/scripts/run_demo.py"
