#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if ! docker ps --filter name=^/serenedb$ --filter status=running --format '{{.Names}}' | grep -qx serenedb; then
  docker start serenedb >/dev/null
fi

exec "$ROOT/.venv/bin/python" -m loglens.agent "$@"
