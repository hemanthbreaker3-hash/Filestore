#!/usr/bin/env bash
# Filestore one-click VPS deployment. Supports only the nine variables below.
# Export them before running this script, or place them in the project .env file.
#   export API_HASH='...'
#   export APP_ID='...'
#   export CHANNEL_ID='-100...'
#   export DATABASE_URL='mongodb+srv://...'
#   export DB_NAME='Filestore'
#   export OWNER='telegram_username'
#   export OWNER_ID='123456789'
#   export PORT='8080'
#   export TG_BOT_TOKEN='...'
#   ./one-click-deploy.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
ENV_FILE="$ROOT/.env"

echo "=== Filestore deployment ==="

# Preserve existing .env values when no shell export is supplied.
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"
write_env() {
  local key="$1" val="${!1:-}"
  if [ -z "$val" ]; then return 0; fi
  if grep -q "^${key}=" "$ENV_FILE"; then
    local escaped
    escaped=$(printf '%s' "$val" | sed 's/[\\&|]/\\&/g')
    sed -i "s|^${key}=.*|${key}=${escaped}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
  fi
}
for key in API_HASH APP_ID CHANNEL_ID DATABASE_URL DB_NAME OWNER OWNER_ID PORT TG_BOT_TOKEN; do
  write_env "$key"
done

# Load .env and verify the complete supported credential set.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
missing=0
for key in API_HASH APP_ID CHANNEL_ID DATABASE_URL DB_NAME OWNER OWNER_ID PORT TG_BOT_TOKEN; do
  if [ -z "${!key:-}" ]; then
    echo "Missing required variable: $key"
    missing=1
  fi
done
if [ "$missing" -ne 0 ]; then
  echo "Set the missing values in .env or export them, then run this script again."
  exit 1
fi

if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y python3 python3-pip python3-venv git curl
fi
if [ ! -d "$ROOT/.venv" ]; then python3 -m venv "$ROOT/.venv"; fi
source "$ROOT/.venv/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

SERVICE_NAME="filestore_bot"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
PYTHON_BIN="$ROOT/.venv/bin/python"
if [ -w /etc/systemd/system ] || sudo -n true 2>/dev/null; then
  sudo tee "$UNIT_PATH" >/dev/null <<UNIT
[Unit]
Description=Filestore Telegram Bot
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$ROOT
EnvironmentFile=$ENV_FILE
ExecStart=$PYTHON_BIN $ROOT/main.py
Restart=always
RestartSec=8

[Install]
WantedBy=multi-user.target
UNIT
  sudo systemctl daemon-reload
  sudo systemctl enable "$SERVICE_NAME"
  sudo systemctl restart "$SERVICE_NAME"
  sudo systemctl --no-pager -l status "$SERVICE_NAME" || true
else
  nohup "$PYTHON_BIN" "$ROOT/main.py" > "$ROOT/bot.log" 2>&1 &
  echo $! > "$ROOT/bot.pid"
  echo "Started in background; log: $ROOT/bot.log"
fi
