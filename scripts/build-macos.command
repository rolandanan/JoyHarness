#!/bin/bash
set -e
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt pyinstaller
.venv/bin/python -m PyInstaller --noconfirm JoyHarness.spec
open dist
