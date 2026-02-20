#!/usr/bin/env bash
set -euo pipefail

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
        echo "NOTE: Microphone and Accessibility permissions are required."
        echo "  These will be requested by macOS on first run."
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

echo ""
echo "=== Setup complete ==="
echo "Run with: ./run.sh"
echo "Or activate manually: source .venv/bin/activate && python -m murmur"
