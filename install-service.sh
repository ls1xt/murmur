#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_NAME="murmur.service"

# Verify venv exists
[ -f "$SCRIPT_DIR/.venv/bin/murmur" ] || { echo "ERROR: Run uv sync first"; exit 1; }

mkdir -p "$SERVICE_DIR"

# Substitute actual project path (service file uses %h which systemd expands,
# but ExecStart needs the real path)
sed "s|%h/dev/python/murmur|$SCRIPT_DIR|g" "$SCRIPT_DIR/$SERVICE_NAME" \
    > "$SERVICE_DIR/$SERVICE_NAME"

systemctl --user daemon-reload
systemctl --user enable --now murmur

echo "Service installed and started."
echo "  Status:  systemctl --user status murmur"
echo "  Logs:    journalctl --user -u murmur -f"
echo "  Stop:    systemctl --user stop murmur"
