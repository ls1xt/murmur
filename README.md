# Murmur

> **Hold F12.** Say *"extract this into a helper function and write a test for it."*
> Release. It appears in Claude Code.

System-wide push-to-talk dictation for any app, any language, zero context switch.

**Free to start** — AssemblyAI gives new accounts $50 in credits, enough for
thousands of sessions before you spend a cent. [Get a free key →](https://www.assemblyai.com/)

[![CI](https://github.com/berleon/murmur/actions/workflows/ci.yml/badge.svg)](https://github.com/berleon/murmur/actions/workflows/ci.yml)

---

## 🎙️ Speak directly to your coding agent

Focus Claude Code, Cursor, or any editor and hold <kbd>F12</kbd>. Your words land as typed
text — no copy-paste, no mode switching. That's the default binding. Nothing to configure.

**Multi-language** — add a second binding for another language. One key for English,
another for German, or any of 90+ languages:

```json
{
  "hotkey": {
    "bindings": [
      { "modifiers": [], "trigger": "KEY_F12", "action": "push_to_talk" },
      { "modifiers": ["KEY_LEFTCTRL", "KEY_LEFTMETA"], "trigger": "KEY_K",
        "action": "push_to_talk", "language": "de" }
    ]
  }
}
```

## ⚡ Go further: voice-triggered automation

Bind a key to inject into a background tmux pane — regardless of which window
you're focused in. Add this to `~/.config/murmur/config.json`:

```json
{
  "hotkey": {
    "bindings": [{
      "modifiers": ["KEY_LEFTCTRL", "KEY_LEFTMETA"],
      "trigger": "KEY_T",
      "action": "toggle",
      "inject_to": "tmux:todo:0.0",
      "append_enter": true
    }]
  }
}
```

Start a tmux session and launch Claude Code in it:

```bash
tmux new-session -d -s todo        # start a detached session named "todo"
tmux send-keys -t todo "claude" Enter  # all voice input now wires directly to Claude
```

Now <kbd>Ctrl</kbd>+<kbd>Cmd</kbd>+<kbd>T</kbd> dictates into that session — Claude Code receives each utterance
as a submitted message and can act on it immediately.

What runs in that pane is up to you. Claude Code in todo-capture mode is one
example — but any process that reads stdin can be a target. Speak a thought and
it gets filed. Speak a task and a workflow kicks off. You're only limited by what's
listening on the other end.

We ship a ready-made script for a silent todo-capture setup:

```bash
./scripts/todo-session.sh
```

> [!WARNING]
> If that pane has a plain shell instead of Claude Code, your dictated words
> execute as shell commands. The same is true any time Murmur injects into a
> focused terminal — speech goes wherever the cursor is. This is what makes it
> powerful. Keep it in mind.

---

## 🔒 Privacy & security

Murmur needs a few permissions to do its job. Here's exactly what it does and doesn't do:

**Keyboard access** — Murmur reads raw key events to detect your hotkey. On Linux
this requires the `input` group; on macOS, Accessibility permission. It does not
log or store keystrokes.

**Audio goes to AssemblyAI** — everything you say while recording is streamed to
their API and transcribed in the cloud. Nothing is stored locally. Review
[AssemblyAI's privacy policy](https://www.assemblyai.com/legal/privacy-policy)
if that matters for your use case.

**Text lands wherever your cursor is** — Murmur injects the transcription as
simulated keystrokes at the focused window. If a terminal or coding agent is
focused, your words arrive there as typed input. Murmur filters out non-speech
content (control characters, untranslated symbols) but is not a full sanitizer.
Be deliberate about what's focused when you speak.

---

## 💻 Platform support

Tested on **macOS Sequoia (Apple Silicon)** and **Linux/Wayland** (Sway).
Other Wayland compositors should work but are untested. X11 and Windows are not supported.
Contributions and test reports welcome.

---

## 📦 Installation

> [!NOTE]
> Packages for Homebrew, AUR, and PyPI are in preparation. Install from source for now:

```bash
git clone https://github.com/berleon/murmur.git
cd murmur
uv sync
uv run murmur --help
```

## 🚀 First run

Set your AssemblyAI API key:

```bash
murmur config --key transcriber.api_key --value YOUR_API_KEY
```

Start the daemon:

```bash
murmur daemon start
```

Default hotkeys:

| Key | Mode | Behaviour |
|-----|------|-----------|
| <kbd>F12</kbd> | Push-to-talk | Hold to record, release to inject |
| <kbd>Ctrl</kbd>+<kbd>Cmd</kbd>+<kbd>M</kbd> *(macOS)* / <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>M</kbd> *(Linux)* | Toggle | Press once to start; press the hotkey again **or type anything** to stop |
| <kbd>Ctrl</kbd>+<kbd>Cmd</kbd>+<kbd>C</kbd> *(macOS)* / <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>C</kbd> *(Linux)* | Clipboard | Hold to record, release to copy transcript to clipboard |

---

## 🛠️ Usage

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

---

## ⚙️ Configuration

Config is stored at `~/.config/murmur/config.json`. The daemon hot-reloads it on
the next keypress — no restart needed.

```bash
murmur config                                                               # view all settings
murmur config --key transcriber.api_key --value K                          # set API key
murmur config --key notify.level --value verbose                           # change notify level
murmur config --key transcriber.keyterms --value "PyTorch,kubectl"         # custom vocab
murmur config --key feedback.start_duration_ms --value 0                   # disable start beep
murmur config --key feedback.stop_duration_ms --value 200                  # longer stop beep
murmur config --key feedback.amplitude --value 0.1                         # quieter beeps
murmur config --key feedback.start_hz --value 440                          # start beep pitch (Hz)
murmur config --key feedback.stop_hz --value 880                           # stop beep pitch (Hz)
murmur config --key transcriber.mic_device --value 2                       # select mic by index
murmur config --key transcriber.reconnect_attempts --value 10              # WebSocket retry count
murmur config --key transcriber.reconnect_delay_ms --value 2000            # initial retry delay
murmur config --key injector.trailing_space --value false                  # no trailing space
murmur config --key injector.key_delay --value 5                           # ms between keystrokes
murmur config --key tray.enabled --value false                             # disable tray icon
murmur config --key log_level --value DEBUG                                # verbose logging
```

Or set the API key via environment variable:

```bash
export ASSEMBLYAI_API_KEY=your_key_here
murmur record
```

### Environment variables

| Variable | Description |
|---|---|
| `ASSEMBLYAI_API_KEY` | AssemblyAI API key (overrides config file) |
| `MURMUR_LOG_LEVEL` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `MURMUR_MIC_DEVICE` | Microphone device index or name |
| `MURMUR_NOTIFY_LEVEL` | Desktop notification level (`off`, `errors`, `verbose`) |
| `MURMUR_INJECT_STRATEGY` | Injection backend (`ydotool`, `clipboard`, `clipboard-fallback`) |
| `DICTATION_HOTKEY_BACKEND` | Hotkey backend override (`evdev`, `pynput`, `auto`) |
| `DICTATION_INJECTOR_BACKEND` | Injector backend override |

### Hotkey bindings

Each binding is independent and fully configurable:

| Field | Default | Description |
|---|---|---|
| `modifiers` | `[]` | Modifier keys (e.g. `["KEY_LEFTCTRL", "KEY_LEFTMETA"]`) |
| `trigger` | — | Trigger key (e.g. `"KEY_F12"`) |
| `action` | `"push_to_talk"` | `push_to_talk`, `toggle`, `copy_to_clipboard` |
| `language` | `null` | Language override for this binding (e.g. `"de"`, `"en_au"`) |
| `inject_to` | `"default"` | `"default"` (focused window) or `"tmux:SESSION:WINDOW.PANE"` |
| `append_enter` | `false` | Send Return keystroke after injection |
| `suppress` | `false` | Swallow the key event (prevents it reaching other apps) |

> [!TIP]
> Push-to-talk works best with dedicated keys (F-keys, mouse buttons). Using
> a letter key as a push-to-talk trigger will type that letter while held. Use
> `toggle` mode instead for modifier+letter combos.

On macOS, `KEY_LEFTALT` is automatically remapped to `KEY_LEFTMETA` (Cmd) at
load time — the same config works on both platforms.

**Supported languages:** 90+ via AssemblyAI — `en`, `en_au`, `en_uk`, `en_us`,
`de`, `fr`, `es`, `it`, `pt`, `nl`, `ja`, `zh`, `ko`, `ru`, `ar`, `hi`, and
[many more](https://www.assemblyai.com/docs/speech-to-text/streaming).

If no language is set, murmur reads `$LANG`/`$LC_ALL` from your environment as a fallback.

**Example config** — see [`examples/config.json`](examples/config.json) for a
complete real-world setup (macOS, multi-language, tmux target).

<details>
<summary>Hotkey advanced settings</summary>

```json
{
  "hotkey": {
    "backend": "auto",
    "evdev_device": "/dev/input/event3",
    "push_to_talk_debounce_ms": 300,
    "stop_on_keypress": true
  }
}
```

| Field | Default | Description |
|---|---|---|
| `backend` | `"auto"` | `"evdev"` (Linux), `"pynput"` (macOS), `"auto"` |
| `evdev_device` | `null` | Pin to a specific `/dev/input/eventN` device |
| `push_to_talk_debounce_ms` | `300` | Ignore key-repeat events shorter than this |
| `stop_on_keypress` | `true` | Stop toggle recording when any non-modifier key is pressed |

</details>

<details>
<summary>Transcriber settings</summary>

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

</details>

<details>
<summary>Injector settings</summary>

```json
{
  "injector": {
    "trailing_space": true,
    "key_delay": 1,
    "inject_strategy": "clipboard"
  }
}
```

| Field | Default | Description |
|---|---|---|
| `trailing_space` | `true` | Append a space after each injected turn |
| `key_delay` | `1` | Milliseconds between keystrokes (increase for slow apps) |
| `inject_strategy` | `"clipboard"` | `"ydotool"`, `"clipboard"`, or `"clipboard-fallback"` |

</details>

<details>
<summary>Feedback settings</summary>

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

</details>

### Selecting a microphone

```bash
murmur list-mics                                              # show all input devices with index
murmur config --key transcriber.mic_device --value 2         # select by index
murmur config --key transcriber.mic_device --value "Scarlett Solo"  # or by name
```

---

## 🐧 System dependencies (Linux)

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

---

## 🔧 Troubleshooting

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

Grant Accessibility permissions: System Settings → Privacy & Security →
Accessibility → add your Terminal or Python.

### Characters dropped in terminals or IDEs

Some apps drop characters when injection is too fast. Increase the key delay:

```bash
murmur config --key injector.key_delay --value 5
```

Or switch to clipboard injection, which pastes the full text at once:

```bash
murmur config --key injector.inject_strategy --value clipboard
```

---

## 🏗️ Architecture

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

---

## 🤝 Contributing

Bug reports and pull requests are welcome.

**Alternative transcription backends are especially wanted.** The codebase has a
clean interface — implement `start(language)`, `stop()`, and wire up three
callbacks (`on_partial`, `on_final`, `on_error`). See
[`murmur/transcriber/base.py`](murmur/transcriber/base.py) and the existing
[AssemblyAI backend](murmur/transcriber/assemblyai.py) as a reference.

Good candidates for new backends:
- [OpenAI Whisper](https://github.com/openai/whisper) (local, no API key needed)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (local, faster)
- [Deepgram](https://deepgram.com/) (streaming API alternative)
- [Whisper.cpp](https://github.com/ggerganov/whisper.cpp) (local, low latency)

Platform reports for other Wayland compositors (Gnome, KDE, Hyprland) are also
very helpful at this stage.

---

## 📄 License

MIT
