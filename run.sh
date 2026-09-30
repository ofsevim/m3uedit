#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3.11 veya üstü gerekli." >&2
    exit 1
fi
exec python3 bootstrap.py "$@"
