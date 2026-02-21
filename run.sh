#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$HOME/.config/murmur/config.json"
OS="$(uname -s)"

fail() { echo "ERROR: $*" >&2; exit 1; }
warn() { echo "WARNING: $*" >&2; }

# --- Shared preflight checks (all platforms) ---

# Check venv
[ -f "$SCRIPT_DIR/.venv/bin/murmur" ] || fail "No venv found. Run: ./setup.sh"

# Check API key
api_key_set=false
if [ -n "${ASSEMBLYAI_API_KEY:-}" ]; then
    api_key_set=true
elif [ -f "$CONFIG_FILE" ] && python3 -c "
import json, sys
data = json.load(open('$CONFIG_FILE'))
sys.exit(0 if data.get('transcriber', {}).get('api_key') else 1)
" 2>/dev/null; then
    api_key_set=true
fi
$api_key_set || fail "No API key configured. Run: ./config-api-key.sh"

# Check sounddevice can query an input device
if ! "$SCRIPT_DIR/.venv/bin/python" -c "import sounddevice; sounddevice.query_devices(kind='input')" &>/dev/null; then
    fail "No audio input device found. Check your microphone and audio system configuration."
fi

# Force Python to use unbuffered I/O so output appears immediately when piped
export PYTHONUNBUFFERED=1

# --- Platform-specific launch ---

case "$OS" in
    Linux*)
        # Check input group
        groups | grep -qw input || warn "Not in 'input' group — hotkey detection may fail. Run: sudo usermod -aG input \$USER"

        # Start ydotoold if not running
        if ! pgrep -x ydotoold > /dev/null 2>&1; then
            echo "Starting ydotoold..."
            systemctl --user start ydotool 2>/dev/null || ydotoold &
            sleep 0.5
            pgrep -x ydotoold > /dev/null 2>&1 || fail "ydotoold failed to start"
        fi

        # Silence PortAudio probe noise (ALSA + JACK warnings from device enumeration)
        export JACK_NO_AUDIO_RESERVATION=1

        "$SCRIPT_DIR/.venv/bin/murmur" "$@" 2> >(grep --line-buffered -v \
            -e "^ALSA lib" \
            -e "^JACK " \
            -e "^Cannot connect to server" \
            -e "^JackShmReadWritePtr" \
            -e "^jack server" \
            -e "^Cannot open device" \
            >&2)
        ;;

    Darwin*)
        # macOS: launch via Murmur.app so that macOS associates the daemon
        # process with the bundle identity com.murmur.daemon.  Users grant
        # Accessibility permission to Murmur.app in System Settings rather
        # than to the raw Python binary (which cannot be added via the UI).
        APP_LAUNCHER="$SCRIPT_DIR/Murmur.app/Contents/MacOS/murmur"
        if [ -x "$APP_LAUNCHER" ]; then
            "$APP_LAUNCHER" "$@"
        else
            # Fallback if the .app bundle is missing (re-run setup.sh)
            "$SCRIPT_DIR/.venv/bin/murmur" "$@"
        fi
        ;;

    *)
        fail "Unsupported OS: $OS (supported: Linux, macOS)"
        ;;
esac
