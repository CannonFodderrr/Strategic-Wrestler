#!/bin/bash
cd "$(dirname "$0")"
echo ""
echo "  Strategic Wrestler"
echo "  ------------------"
echo "  Checking for updates from GitHub, then starting..."
echo ""

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "  ERROR: Python 3 not found."
  echo "  On Chromebook Linux try:  sudo apt update && sudo apt install -y python3"
  read -r -p "  Press Enter to exit…"
  exit 1
fi

if [ ! -f "update_and_serve.py" ]; then
  echo "  ERROR: update_and_serve.py not found in this folder."
  read -r -p "  Press Enter to exit…"
  exit 1
fi

exec "$PY" update_and_serve.py
