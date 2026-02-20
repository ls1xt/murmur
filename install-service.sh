#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OS="$(uname -s)"

# Verify venv exists
[ -f "$SCRIPT_DIR/.venv/bin/murmur" ] || { echo "ERROR: Run ./setup.sh first (venv not found)"; exit 1; }

case "$OS" in
    Linux*)
        SERVICE_DIR="$HOME/.config/systemd/user"
        SERVICE_NAME="murmur.service"

        mkdir -p "$SERVICE_DIR"

        sed "s|@@MURMUR_DIR@@|$SCRIPT_DIR|g" "$SCRIPT_DIR/$SERVICE_NAME" \
            > "$SERVICE_DIR/$SERVICE_NAME"

        systemctl --user daemon-reload
        systemctl --user enable --now murmur

        echo "Service installed and started."
        echo "  Status:  systemctl --user status murmur"
        echo "  Logs:    journalctl --user -u murmur -f"
        echo "  Stop:    systemctl --user stop murmur"
        ;;

    Darwin*)
        PLIST_DIR="$HOME/Library/LaunchAgents"
        PLIST_NAME="com.murmur.daemon.plist"

        mkdir -p "$PLIST_DIR"

        sed "s|@@MURMUR_DIR@@|$SCRIPT_DIR|g" "$SCRIPT_DIR/murmur.plist" \
            > "$PLIST_DIR/$PLIST_NAME"

        launchctl load "$PLIST_DIR/$PLIST_NAME"

        echo "LaunchAgent installed and started."
        echo "  Status:  launchctl list | grep murmur"
        echo "  Logs:    tail -f /tmp/murmur.log"
        echo "  Stop:    launchctl stop com.murmur.daemon"
        ;;

    *)
        echo "ERROR: Unsupported OS: $OS"
        echo "Supported: Linux, macOS (Darwin)"
        exit 1
        ;;
esac
