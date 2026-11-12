#!/usr/bin/env bash
# Optional: refresh OS packages (safe subset)
set -euo pipefail
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y python3 python3-pip python3-venv git curl
elif command -v pkg >/dev/null 2>&1; then
  # Termux
  pkg update -y
  pkg install -y python git
fi
echo "System tools ready."
