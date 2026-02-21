#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Murmur Setup ==="
echo ""

OS="$(uname -s)"

case "$OS" in
    Linux*)
        # Detect distro via /etc/os-release
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            DISTRO="${ID:-unknown}"
        else
            DISTRO="unknown"
        fi

        echo "Detected: Linux ($DISTRO)"
        echo ""

        # Install system dependencies
        case "$DISTRO" in
            arch|manjaro|endeavouros)
                echo "Installing system dependencies via pacman..."
                sudo pacman -S --needed ydotool portaudio
                ;;
            ubuntu|debian|linuxmint|pop)
                echo "Installing system dependencies via apt..."
                sudo apt-get install -y ydotool portaudio19-dev
                ;;
            fedora)
                echo "Installing system dependencies via dnf..."
                sudo dnf install -y ydotool portaudio-devel
                ;;
            *)
                echo "WARNING: Unknown distro '$DISTRO'. Install ydotool and portaudio manually."
                ;;
        esac

        echo ""

        # Check input group membership
        if ! groups | grep -qw input; then
            echo "WARNING: You are not in the 'input' group."
            echo "  Run: sudo usermod -aG input \$USER"
            echo "  Then log out and back in."
            echo ""
        fi

        # Check ydotoold status
        if ! pgrep -x ydotoold > /dev/null 2>&1; then
            echo "WARNING: ydotoold daemon is not running."
            echo "  Start it: systemctl --user start ydotool"
            echo ""
        fi
        ;;

    Darwin*)
        echo "Detected: macOS"
        echo ""

        # Check for Homebrew
        if ! command -v brew &> /dev/null; then
            echo "ERROR: Homebrew is required but not installed."
            echo "  Install: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            exit 1
        fi

        echo "Installing system dependencies via Homebrew..."
        brew install portaudio

        echo ""
        ;;

    *)
        echo "ERROR: Unsupported OS: $OS"
        echo "Supported: Linux, macOS (Darwin)"
        exit 1
        ;;
esac

# Create venv and install (both platforms)
echo "Running uv sync..."
uv sync

# Create/refresh Murmur.app bundle on macOS so hotkeys can be granted
# Accessibility permission via System Settings (raw Python binaries cannot
# be added to the Accessibility list through the UI).
if [ "$OS" = "Darwin" ]; then
    APP_DIR="$SCRIPT_DIR/Murmur.app/Contents"
    mkdir -p "$APP_DIR/MacOS"

    cat > "$APP_DIR/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>com.murmur.daemon</string>
    <key>CFBundleName</key>
    <string>Murmur</string>
    <key>CFBundleDisplayName</key>
    <string>Murmur</string>
    <key>CFBundleExecutable</key>
    <string>murmur</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSAccessibilityUsageDescription</key>
    <string>Murmur needs Accessibility access to detect global hotkeys for voice dictation.</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>Murmur needs Microphone access to capture audio for voice dictation.</string>
</dict>
</plist>
EOF

    # Write the launcher — exec replaces the shell with Python so that the
    # process runs under the bundle's macOS identity (com.murmur.daemon).
    cat > "$APP_DIR/MacOS/murmur" << 'LAUNCHER'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"
MURMUR_BIN="$PROJECT_DIR/.venv/bin/murmur"
if [ ! -f "$MURMUR_BIN" ]; then
    osascript -e 'display alert "Murmur" message "murmur not found in .venv. Run ./setup.sh first." as critical' 2>/dev/null || true
    echo "ERROR: $MURMUR_BIN not found. Run ./setup.sh first." >&2
    exit 1
fi
export PYTHONUNBUFFERED=1
exec "$MURMUR_BIN" "$@"
LAUNCHER

    chmod +x "$APP_DIR/MacOS/murmur"

    if codesign --force --deep --sign - "$SCRIPT_DIR/Murmur.app" 2>/dev/null; then
        echo "Murmur.app created and signed (bundle ID: com.murmur.daemon)"
    else
        echo "WARNING: codesign failed; Murmur.app created but unsigned"
    fi

    echo ""
    echo "NEXT STEP (required for hotkeys):"
    echo "  Open System Settings → Privacy & Security → Accessibility"
    echo "  Click + and add:  $SCRIPT_DIR/Murmur.app"
    echo ""
fi

echo ""
echo "=== Setup complete ==="
echo "Run with: ./run.sh"
echo "Or activate manually: source .venv/bin/activate && python -m murmur"
