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
- Auto-reconnect on WebSocket drop — exponential backoff, configurable attempts
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
murmur list-mics                       # list available microphone devices
murmur record                          # single dictation session
murmur record --inject-partials        # stream partial transcripts as you speak
murmur record --inject ydotool         # force ydotool injection backend
murmur record --notify verbose         # verbose desktop notifications
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
murmur config --key feedback.start_hz --value 440                   # start beep pitch (Hz)
murmur config --key feedback.stop_hz --value 880                    # stop beep pitch (Hz)
murmur config --key transcriber.mic_device --value 2                # select mic by index
murmur config --key transcriber.reconnect_attempts --value 10       # WebSocket retry count
murmur config --key transcriber.reconnect_delay_ms --value 2000     # initial retry delay
murmur config --key injector.trailing_space --value false           # no trailing space
murmur config --key injector.key_delay --value 5                    # ms between keystrokes
murmur config --key tray.enabled --value false                      # disable tray icon
murmur config --key log_level --value DEBUG                         # verbose logging
```

Or set the API key via environment variable:

```bash
export ASSEMBLYAI_API_KEY=your_key_here
murmur record
```

### Environment Variables

| Variable | Description |
|---|---|
| `ASSEMBLYAI_API_KEY` | AssemblyAI API key (overrides config file) |
| `MURMUR_LOG_LEVEL` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `MURMUR_MIC_DEVICE` | Microphone device index or name |
| `MURMUR_NOTIFY_LEVEL` | Desktop notification level (`off`, `errors`, `verbose`) |
| `MURMUR_INJECT_STRATEGY` | Injection backend (`ydotool`, `clipboard`, `clipboard-fallback`) |
| `DICTATION_HOTKEY_BACKEND` | Hotkey backend override (`evdev`, `pynput`, `auto`) |
| `DICTATION_INJECTOR_BACKEND` | Injector backend override |

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

### Example Config

See [`examples/config.json`](examples/config.json) for a complete real-world config (macOS, multi-language, tmux target). Copy it to `~/.config/murmur/config.json` and replace `YOUR_API_KEY`.

On Linux, swap `"inject_strategy": "pynput"` → `"ydotool"` and `KEY_LEFTMETA` → `KEY_LEFTALT` in the modifier lists.

### Hotkey Advanced Settings

```json
{
  "hotkey": {
    "backend": "auto",
    "evdev_device": "/dev/input/event3",
    "push_to_talk_debounce_ms": 300
  }
}
```

| Field | Default | Description |
|---|---|---|
| `backend` | `"auto"` | `"evdev"` (Linux), `"pynput"` (macOS), `"auto"` |
| `evdev_device` | `null` | Pin to a specific `/dev/input/eventN` device |
| `push_to_talk_debounce_ms` | `300` | Ignore key-repeat events shorter than this |

### Transcriber Settings

```json
{
  "transcriber": {
    "language": "en",
    "keyterms": ["kubectl", "PyTorch"],
    "inject_partials": false,
    "reconnect_attempts": 5,
    "reconnect_delay_ms": 1000,
    "mic_device": null,
    "format_turns": true,
    "end_of_turn_confidence_threshold": 0.4,
    "min_end_of_turn_silence_when_confident": 400,
    "max_turn_silence": 1280
  }
}
```

| Field | Default | Description |
|---|---|---|
| `language` | `"en"` | Default language (overridden per-binding) |
| `keyterms` | `[]` | Words to boost in transcription accuracy |
| `inject_partials` | `false` | Stream partial transcripts as you speak (may produce corrections) |
| `reconnect_attempts` | `5` | WebSocket reconnect retries on unexpected drop |
| `reconnect_delay_ms` | `1000` | Initial delay between reconnect attempts (doubles each try) |
| `mic_device` | `null` | Mic device index or name (`murmur list-mics` to find) |
| `format_turns` | `true` | Apply punctuation and casing formatting |
| `end_of_turn_confidence_threshold` | `0.4` | AssemblyAI end-of-turn sensitivity |
| `min_end_of_turn_silence_when_confident` | `400` | Silence (ms) before committing a turn |
| `max_turn_silence` | `1280` | Max silence (ms) before forcing a turn end |

### Injector Settings

```json
{
  "injector": {
    "trailing_space": true,
    "key_delay": 0,
    "inject_strategy": "clipboard"
  }
}
```

| Field | Default | Description |
|---|---|---|
| `trailing_space` | `true` | Append a space after each injected turn |
| `key_delay` | `0` | Milliseconds between keystrokes (increase for slow apps) |
| `inject_strategy` | `"clipboard"` | `"ydotool"`, `"clipboard"`, or `"clipboard-fallback"` |

### Feedback Settings

```json
{
  "feedback": {
    "audio_enabled": true,
    "start_hz": 440.0,
    "stop_hz": 880.0,
    "start_duration_ms": 100,
    "stop_duration_ms": 100,
    "amplitude": 0.3
  }
}
```

| Field | Default | Description |
|---|---|---|
| `audio_enabled` | `true` | Enable start/stop beeps |
| `start_hz` | `440.0` | Start beep pitch in Hz |
| `stop_hz` | `880.0` | Stop beep pitch in Hz |
| `start_duration_ms` | `100` | Start beep duration; set to `0` to disable |
| `stop_duration_ms` | `100` | Stop beep duration; set to `0` to disable |
| `amplitude` | `0.3` | Beep volume (0.0–1.0) |

### Selecting a Microphone

```bash
murmur list-mics               # show all input devices with index
murmur config --key transcriber.mic_device --value 2   # select by index
murmur config --key transcriber.mic_device --value "Scarlett Solo"  # or by name
```

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

### Characters dropped in terminals or IDEs

Some apps drop characters when injection is too fast. Increase the key delay:

```bash
murmur config --key injector.key_delay --value 5
```

Or switch to clipboard injection, which pastes the full text at once:

```bash
murmur config --key injector.inject_strategy --value clipboard
```

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
