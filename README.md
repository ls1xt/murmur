# 🎤 Dictation — System-Wide Voice-to-Text

Push-to-talk dictation that works in **any application** on Linux (Wayland) and macOS.  
Hold a hotkey, speak, release — your words appear at the cursor.

## How It Works

```
Hotkey held ──► Mic streams to AssemblyAI ──► Transcript injected via ydotool
  (evdev)           (Universal-Streaming v3)        (kernel uinput)
```

| Component       | Linux (Wayland)              | macOS               |
|-----------------|------------------------------|----------------------|
| Hotkey listener | `evdev` (reads /dev/input)   | `pynput`            |
| Transcription   | AssemblyAI streaming API     | AssemblyAI          |
| Text injection  | `ydotool` (kernel uinput)    | `pynput` controller |

## Quick Start (Linux Wayland)

### 1. System dependencies

```bash
# Ubuntu/Debian
sudo apt install ydotool portaudio19-dev python3-dev

# Fedora
sudo dnf install ydotool portaudio-devel python3-devel

# Arch
sudo pacman -S ydotool portaudio
```

### 2. Permissions

```bash
# Add yourself to the input group (needed for evdev + ydotool)
sudo usermod -aG input $USER

# Log out and back in (or: newgrp input)
```

### 3. Start ydotoold daemon

```bash
# As a user service (persistent)
systemctl --user enable ydotool
systemctl --user start ydotool

# Or one-off
ydotoold &
```

### 4. Install Python package

```bash
pip install assemblyai pyaudio evdev
# or from this directory:
pip install -e .
```

### 5. Get an AssemblyAI API key

Sign up at [assemblyai.com](https://www.assemblyai.com/) — you get $50 in free credits.

### 6. Run

```bash
export ASSEMBLYAI_API_KEY=your_key_here
python -m dictation
```

Then **hold Ctrl+Shift+Space** and speak. Release to stop. Text appears wherever your cursor is.

## Configuration

Configuration is loaded from (in order of priority):
1. Environment variables (highest)
2. `~/.config/dictation/config.json`
3. Built-in defaults

### Environment Variables

| Variable                     | Description                      | Default          |
|------------------------------|----------------------------------|------------------|
| `ASSEMBLYAI_API_KEY`         | Your AssemblyAI API key          | *(required)*     |
| `DICTATION_LOG_LEVEL`        | Logging level                    | `INFO`           |
| `DICTATION_HOTKEY_MODE`      | `push_to_talk` or `toggle`       | `push_to_talk`   |
| `DICTATION_HOTKEY_BACKEND`   | `evdev`, `pynput`, or `auto`     | `auto`           |
| `DICTATION_INJECTOR_BACKEND` | `ydotool`, `pynput`, or `auto`   | `auto`           |

### Config File Example

```json
{
  "hotkey": {
    "modifiers": ["KEY_LEFTCTRL", "KEY_LEFTSHIFT"],
    "trigger": "KEY_SPACE",
    "mode": "push_to_talk",
    "backend": "auto"
  },
  "transcriber": {
    "backend": "assemblyai",
    "sample_rate": 16000,
    "format_turns": true,
    "language": "en"
  },
  "injector": {
    "backend": "auto",
    "trailing_space": true,
    "key_delay": 0
  },
  "feedback": {
    "audio_enabled": true
  },
  "log_level": "INFO"
}
```

## Architecture

```
dictation/
├── __init__.py
├── __main__.py          # python -m dictation
├── main.py              # DictationApp orchestrator
├── config.py            # Dataclass-based configuration
├── hotkey/
│   ├── base.py          # HotkeyListener ABC
│   ├── evdev_listener.py    # Wayland-native (reads /dev/input)
│   └── pynput_listener.py   # macOS/X11 fallback
├── transcriber/
│   ├── base.py          # Transcriber ABC
│   └── assemblyai_transcriber.py  # AssemblyAI Universal-Streaming v3
├── injector/
│   ├── base.py          # TextInjector ABC
│   ├── ydotool_injector.py  # Linux (Wayland + X11)
│   └── pynput_injector.py   # macOS
└── feedback/
    └── audio_feedback.py    # Beep sounds via PyAudio
```

Every component has an abstract base class, making it straightforward to add new backends (e.g. local Whisper, dotool, wtype).

## Troubleshooting

### "No keyboard devices found"

You need to be in the `input` group:
```bash
sudo usermod -aG input $USER
# Then log out and back in
```

### ydotool types nothing / "ydotoold not running"

```bash
# Check daemon status
systemctl --user status ydotool

# Start it
systemctl --user start ydotool
# or manually:
ydotoold &

# Test it
ydotool type "hello world"
```

### PyAudio installation fails

Install the system PortAudio library first:
```bash
# Ubuntu/Debian
sudo apt install portaudio19-dev

# Fedora
sudo dnf install portaudio-devel

# macOS
brew install portaudio
```

### Hotkey not detected

On **Wayland**, pynput keyboard monitoring doesn't work. The tool auto-selects evdev on Linux, which reads directly from the kernel input subsystem. Make sure you're in the `input` group.

On **macOS**, grant Accessibility permissions: System Settings → Privacy & Security → Accessibility → add your Terminal or Python.

## Adding a New Backend

Each component uses an ABC pattern. To add a new transcriber (e.g. local Whisper):

1. Create `transcriber/whisper_transcriber.py` implementing `Transcriber`
2. Add a case to the factory in `transcriber/__init__.py`
3. Add `"whisper"` as a backend option in `TranscriberConfig`

Same pattern for hotkey listeners and injectors.

## License

MIT
