#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname "$SCRIPT_DIR")
export PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/seo-hub-pycache"

cd "$PROJECT_DIR"
python3 server.py --weekly "$@"
