# Murmur — System-Wide Voice Dictation

[![CI](https://github.com/berleon/murmur/actions/workflows/ci.yml/badge.svg)](https://github.com/berleon/murmur/actions/workflows/ci.yml)

Push-to-talk dictation that works in **any application** on Linux (Wayland) and macOS.
Hold a hotkey, speak, release — your words appear at the cursor.

## Installation

### macOS

```bash
brew tap berleon/murmur
brew install murmur
```

### Linux (Arch)

```bash
yay -S python-murmur
```

### Linux (Debian/Ubuntu)

Download the latest `.deb` from [Releases](https://github.com/berleon/murmur/releases) and install:

```bash
sudo dpkg -i murmur_*.deb
```

Or build from source:

```bash
./packaging/deb/build-deb.sh
```

### Any platform (PyPI)

```bash
pip install murmur-dictation
# or with uv:
uv tool install murmur-dictation
```

### From source

```bash
git clone https://github.com/berleon/murmur.git
cd murmur
uv sync
uv run murmur --help
```

## First Run

After installing, set your AssemblyAI API key:

```bash
murmur config --key transcriber.api_key --value YOUR_API_KEY
```

Get a free key at https://www.assemblyai.com/

Then start the daemon:

```bash
murmur daemon start
```

## Usage

```
murmur config                          # view config
murmur config --key KEY --value VALUE  # set config value
murmur record                          # single dictation session
murmur daemon start                    # start background daemon
murmur daemon stop                     # stop daemon
murmur daemon status                   # check if running
murmur daemon enable                   # install as system service
```

Default hotkeys:

| Key | Mode | Behaviour |
|-----|------|-----------|
| **F12** | Push-to-talk | Hold to record, release to inject |
| **Ctrl+Alt+M** | Toggle | Press once to start, press again to stop |
| **Ctrl+Alt+C** | Clipboard | Hold to record, release copies to clipboard |

## How It Works

```
Hotkey held ──► Mic streams to AssemblyAI ──► Transcript injected
  (evdev)          (Universal-Streaming v3)      (ydotool/pynput)
```

| Component       | Linux (Wayland)              | macOS               |
|-----------------|------------------------------|----------------------|
| Hotkey listener | `evdev` (reads /dev/input)   | `pynput`            |
| Transcription   | AssemblyAI streaming API     | AssemblyAI          |
| Text injection  | `ydotool` (kernel uinput)    | `pynput` controller |

## System Dependencies (Linux)

```bash
# Ubuntu/Debian
sudo apt install ydotool portaudio19-dev python3-dev

# Fedora
sudo dnf install ydotool portaudio-devel python3-devel

# Arch
sudo pacman -S ydotool portaudio
```

Add yourself to the input group (needed for evdev + ydotool):

```bash
sudo usermod -aG input $USER
# Log out and back in (or: newgrp input)
```

## Configuration

Config is stored at `~/.config/murmur/config.json`.

```bash
murmur config                                       # view all settings
murmur config --key transcriber.api_key --value K  # set API key
murmur config --key notify.level --value verbose                     # change notify level
murmur config --key transcriber.keyterms --value "PyTorch,kubectl"  # custom vocab
murmur config --key feedback.start_duration_ms --value 0            # disable start beep
murmur config --key feedback.stop_duration_ms --value 200           # longer stop beep
murmur config --key feedback.amplitude --value 0.1                  # quieter beeps
```

Or set the API key via environment variable:

```bash
export ASSEMBLYAI_API_KEY=your_key_here
murmur record
```

## Troubleshooting

### "No keyboard devices found"

You need to be in the `input` group:

```bash
sudo usermod -aG input $USER
# Then log out and back in
```

### ydotool types nothing / "ydotoold not running"

```bash
systemctl --user enable ydotool
systemctl --user start ydotool
# test: ydotool type "hello world"
```

### Hotkey not detected on macOS

Grant Accessibility permissions: System Settings → Privacy & Security → Accessibility → add your Terminal or Python.

## Architecture

```
murmur/
├── main.py              # CLI entry point (config, record, daemon subcommands)
├── app.py               # DictationApp — hotkey → transcriber → injector pipeline
├── config.py            # Dataclass-based configuration
├── setup_wizard.py      # First-run setup (GUI or terminal)
├── hotkey/              # evdev (Linux) or pynput (macOS) listeners
├── transcriber/         # AssemblyAI streaming transcription
├── injector/            # ydotool (Linux) or pynput (macOS) text injection
└── feedback/            # Audio feedback, desktop notifications, tray icon
```

## License

MIT
