#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$HOME/.config/murmur/config.json"

fail() { echo "ERROR: $*" >&2; exit 1; }
warn() { echo "WARNING: $*" >&2; }

# Check venv
[ -f "$SCRIPT_DIR/.venv/bin/murmur" ] || fail "No venv found. Run: uv sync"

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

# Check PyAudio initializes without crashing (catches e.g. missing pipewire-alsa)
if ! "$SCRIPT_DIR/.venv/bin/python" -c "import pyaudio; p = pyaudio.PyAudio(); p.terminate()" &>/dev/null; then
    fail "PyAudio failed to initialize (audio system may be misconfigured).\n  On PipeWire systems: sudo pacman -S pipewire-alsa (or distro equivalent)"
fi

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

exec "$SCRIPT_DIR/.venv/bin/murmur" "$@" 2> >(grep -v \
    -e "^ALSA lib" \
    -e "^JACK " \
    -e "^Cannot connect to server" \
    -e "^JackShmReadWritePtr" \
    -e "^jack server" \
    -e "^Cannot open device" \
    >&2)
