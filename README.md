# Murmur

> **Hold F12.** Say *"extract this into a helper function and write a test for it."*
> Release. It appears in Claude Code.

System-wide push-to-talk dictation for any app, any language, zero context switch.

**Free to start** — AssemblyAI gives new accounts $50 in credits, enough for
thousands of sessions before you spend a cent. [Get a free key →](https://www.assemblyai.com/)

[![CI](https://github.com/ls1xt/murmur/actions/workflows/ci.yml/badge.svg)](https://github.com/ls1xt/murmur/actions/workflows/ci.yml)

---

## What you can do

- **Speak into any app** — Claude Code, Cursor, VS Code, browsers, terminals. No copy-paste, no mode switching.
- **Push-to-talk or toggle** — hold a key to record and release to inject, or press once to start and again to stop
- **Clipboard mode** — capture speech to clipboard instead of typing it in
- **Voice → tmux automation** — dictate into a background pane regardless of what window you're focused on; wire Claude Code to it and each utterance becomes a submitted message
- **Multi-language** — bind separate hotkeys for different languages; 90+ via AssemblyAI
- **Custom vocabulary** — add project-specific terms (class names, CLIs, abbreviations) to boost transcription accuracy

---

## Installation

**macOS — Homebrew (recommended):**

```bash
brew tap ls1xt/murmur https://github.com/ls1xt/homebrew-murmur
brew install --HEAD ls1xt/murmur/murmur
```

> [!NOTE]
> `--HEAD` installs the latest development build. A stable release is coming soon.

**From source (macOS & Linux):**

```bash
git clone https://github.com/ls1xt/murmur.git
cd murmur
uv sync
uv run murmur --help
```

---

## Quick start

**1.** Get a free API key at [assemblyai.com](https://www.assemblyai.com/)

**2.** Set it:
```bash
murmur config --key transcriber.api_key --value YOUR_API_KEY
```

**3.** Start the daemon:
```bash
murmur daemon start
```

**4.** Test it: focus any text field, hold <kbd>F12</kbd>, say something, release. Your words appear.

To run at login: `murmur daemon enable`

> [!NOTE]
> **Linux users:** you need to be in the `input` group and have `ydotool` running before step 3.
> See [System setup (Linux)](#-system-setup-linux) below.

---

## Default hotkeys

| Key | Mode | Behaviour |
|-----|------|-----------|
| <kbd>F12</kbd> | Push-to-talk | Hold to record, release to inject |
| <kbd>Ctrl</kbd>+<kbd>Cmd</kbd>+<kbd>M</kbd> *(macOS)* / <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>M</kbd> *(Linux)* | Toggle | Press to start; press again or type anything to stop |
| <kbd>Ctrl</kbd>+<kbd>Cmd</kbd>+<kbd>C</kbd> *(macOS)* / <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>C</kbd> *(Linux)* | Clipboard | Hold to record, release to copy transcript |

---

## 🎙️ Speak directly to your coding agent

Focus Claude Code, Cursor, or any editor and hold <kbd>F12</kbd>. Your words land as typed
text — no copy-paste, no mode switching. That's the default binding. Nothing to configure.

**Multi-language** — bind a second key for another language. One key for English,
another for German, or any of 90+ languages:

```json
{
  "hotkey": {
    "bindings": [
      { "modifiers": [], "trigger": "KEY_F12", "mode": "push_to_talk" },
      { "modifiers": ["KEY_LEFTCTRL", "KEY_LEFTMETA"], "trigger": "KEY_K",
        "mode": "push_to_talk", "language": "de" }
    ]
  }
}
```

## ⚡ Voice-triggered automation

Bind a key to inject into a background tmux pane — regardless of which window
you're focused in. Add this to `~/.config/murmur/config.json`:

```json
{
  "hotkey": {
    "bindings": [{
      "modifiers": ["KEY_LEFTCTRL", "KEY_LEFTMETA"],
      "trigger": "KEY_T",
      "mode": "toggle",
      "destination": "tmux:todo:0.0",
      "append_enter": true
    }]
  }
}
```

Start a tmux session and run `claude` in it:

```bash
tmux new-session -d -s todo
```

Now <kbd>Ctrl</kbd>+<kbd>Cmd</kbd>+<kbd>T</kbd> dictates directly into Claude Code — each utterance becomes
a submitted message. A ready-made todo-capture script is included: `./scripts/todo-session.sh`

> [!WARNING]
> If that pane has a plain shell instead of Claude Code, your dictated words
> execute as shell commands. The same is true any time Murmur injects into a
> focused terminal. Be deliberate about what's focused when you speak.

---

## 🔒 Privacy & security

**Keyboard access** — Murmur reads raw key events to detect your hotkey. On Linux
this requires the `input` group; on macOS, Accessibility permission. It does not
log or store keystrokes.

**Audio goes to AssemblyAI** — everything you say while recording is streamed to
their API and transcribed in the cloud. Nothing is stored locally. Review
[AssemblyAI's privacy policy](https://www.assemblyai.com/legal/privacy-policy)
if that matters for your use case.

**Text lands wherever your cursor is** — Murmur injects the transcription as
simulated keystrokes at the focused window. Murmur filters out non-speech
content but is not a full sanitizer. Be deliberate about what's focused when you speak.

---

## 💻 Platform support

Tested on **macOS Sequoia (Apple Silicon)** and **Linux/Wayland** (Sway).
Other Wayland compositors should work but are untested. X11 and Windows are not supported.
Contributions and test reports welcome.

---

## ⚙️ Configuration

Config is stored at `~/.config/murmur/config.json`. The daemon hot-reloads it on
the next keypress — no restart needed.

```bash
murmur config                          # view current config
murmur config --key KEY --value VALUE  # set a value
murmur list-mics                       # list microphone devices
```

See [`docs/configuration.md`](docs/configuration.md) for the full reference, or
[`examples/config.json`](examples/config.json) for a complete real-world setup.

---

## 🐧 System setup (Linux)

```bash
# Ubuntu/Debian
sudo apt install ydotool portaudio19-dev python3-dev

# Fedora
sudo dnf install ydotool portaudio-devel python3-devel

# Arch
sudo pacman -S ydotool portaudio
```

Add yourself to the `input` group (needed for evdev + ydotool):

```bash
sudo usermod -aG input $USER
# Log out and back in (or: newgrp input)
```

Enable ydotool:

```bash
systemctl --user enable --now ydotool
```

---

## 🍎 System setup (macOS)

Murmur reads global key events and injects text — both require **Accessibility** permission
for the app that runs murmur (your terminal, or the murmur binary itself when running as a daemon).

Grant it before starting the daemon to avoid a silent failure:

**System Settings → Privacy & Security → Accessibility → add your terminal app**
(Terminal, iTerm2, Alacritty, Ghostty, etc.)

If you installed via Homebrew and use `murmur daemon enable` (launchd), you may also need
to add the `murmur` or `python3` binary directly when prompted by macOS.

No other system dependencies are required on macOS.

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

## 🤖 AI-assisted setup

Let your AI assistant handle the setup. Pipe the setup guide into Claude Code:

```bash
curl -sL https://raw.githubusercontent.com/ls1xt/murmur/main/AI_SETUP.md | claude
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

<details>
<summary>Architecture</summary>

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

</details>

---

## 📄 License

MIT
