#!/bin/bash
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python -m src "$@"
fi
exec python3 -m src "$@"
