# Murmur — System-Wide Voice Dictation

[![CI](https://github.com/berleon/murmur/actions/workflows/ci.yml/badge.svg)](https://github.com/berleon/murmur/actions/workflows/ci.yml)

Push-to-talk dictation that works in **any application** on Linux (Wayland) and macOS.
Hold a hotkey, speak, release — your words appear at the cursor.

**Features:**
- Multiple independent hotkey bindings — push-to-talk, toggle, clipboard, per-binding language
- Per-binding language — one key for English, another for German, 90+ languages via AssemblyAI
- Per-binding injection target — dictate into a fixed tmux pane regardless of window focus
- `append_enter` — automatically submit after injection (great for CLI and chat)
- Hot config reload — edit `~/.config/murmur/config.json` live, no daemon restart needed
- Single config for Linux + macOS — `KEY_LEFTALT` auto-remaps to Cmd on macOS
- Locale-aware default language — reads `$LANG`/`$LC_ALL` if no language is configured
- Audio feedback beeps, system tray icon, desktop notifications

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
| **Ctrl+Cmd+M** *(macOS)* / **Ctrl+Alt+M** *(Linux)* | Toggle | Press once to start, press again to stop |
| **Ctrl+Cmd+C** *(macOS)* / **Ctrl+Alt+C** *(Linux)* | Clipboard | Hold to record, release copies to clipboard |

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

Config is stored at `~/.config/murmur/config.json`. The daemon hot-reloads it on the next keypress — no restart needed.

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

### Hotkey Bindings

Each binding is independent and fully configurable. Per-binding fields:

| Field | Default | Description |
|---|---|---|
| `modifiers` | `[]` | Modifier keys (e.g. `["KEY_LEFTCTRL", "KEY_LEFTMETA"]`) |
| `trigger` | — | Trigger key (e.g. `"KEY_F12"`) |
| `action` | `"push_to_talk"` | `push_to_talk`, `toggle`, `copy_to_clipboard` |
| `language` | `null` | Language override for this binding (e.g. `"de"`, `"en_au"`) |
| `inject_to` | `"default"` | `"default"` (focused window) or `"tmux:SESSION:WINDOW.PANE"` |
| `append_enter` | `false` | Send Return keystroke after injection |
| `suppress` | `false` | Swallow the key event (prevents it reaching other apps) |

**Example — multi-language + tmux setup:**

```json
{
  "hotkey": {
    "bindings": [
      {
        "modifiers": [], "trigger": "KEY_F12",
        "action": "push_to_talk", "suppress": true
      },
      {
        "modifiers": ["KEY_LEFTCTRL", "KEY_LEFTALT"], "trigger": "KEY_M",
        "action": "toggle"
      },
      {
        "modifiers": ["KEY_LEFTCTRL", "KEY_LEFTALT"], "trigger": "KEY_K",
        "action": "push_to_talk", "language": "de"
      },
      {
        "modifiers": ["KEY_LEFTCTRL", "KEY_LEFTALT"], "trigger": "KEY_T",
        "action": "push_to_talk",
        "inject_to": "tmux:todo:0.0",
        "append_enter": true
      }
    ]
  }
}
```

On macOS, `KEY_LEFTALT` is automatically remapped to `KEY_LEFTMETA` (Cmd) at load time, so the same config works on both platforms.

**Supported languages:** 90+ via AssemblyAI — `en`, `en_au`, `en_uk`, `en_us`, `de`, `fr`, `es`, `it`, `pt`, `nl`, `ja`, `zh`, `ko`, `ru`, `ar`, `hi`, and [many more](https://www.assemblyai.com/docs/speech-to-text/streaming).

If no language is set, murmur reads `$LANG`/`$LC_ALL` from your environment as a fallback.

### Dictating into a tmux pane

Bind a key to `inject_to: "tmux:SESSION:WINDOW.PANE"` to always send transcription to a specific pane — regardless of which window is focused. Combine with `append_enter: true` to auto-submit each utterance.

Example — a voice-driven todo log with Claude Code:

```bash
# Start a persistent todo session
./scripts/todo-session.sh

# Now Ctrl+Alt+T (or Ctrl+Cmd+T on macOS) dictates directly into Claude
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
├── config.py            # Dataclass-based configuration with hot-reload
├── language.py          # Language enum (90+ codes) + locale detection
├── setup_wizard.py      # First-run setup (GUI or terminal)
├── hotkey/              # evdev (Linux) or pynput (macOS) listeners
├── transcriber/         # AssemblyAI streaming transcription
├── injector/            # ydotool / pynput / CGEvent / tmux text injection
└── feedback/            # Audio feedback, desktop notifications, tray icon
```

## License

MIT
