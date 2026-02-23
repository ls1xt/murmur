# Murmur AI Setup Guide

This file is designed to be piped into an AI assistant to guide interactive setup:

```bash
curl -sL https://raw.githubusercontent.com/ls1xt/murmur/main/AI_SETUP.md | claude
```

---

## What is murmur?

Murmur is a system-wide push-to-talk dictation tool for macOS and Linux/Wayland.
It transcribes speech via AssemblyAI and injects the result as typed text into
whatever window is focused — or into a specific tmux pane. Common use: dictate
directly into Claude Code, Cursor, or any editor without copy-pasting.

---

## Your job

Help the user get murmur fully working on their system. Work through each step
below in order, running commands for them where possible, and checking in when
a decision or manual action is needed.

---

## Step 1: Detect platform

Determine whether the user is on macOS or Linux (and which distro if Linux).
Wayland is required on Linux — X11 is not supported.

---

## Step 2: Install system dependencies

**Linux:**

```bash
# Ubuntu/Debian
sudo apt install ydotool portaudio19-dev python3-dev

# Fedora
sudo dnf install ydotool portaudio-devel python3-devel

# Arch
sudo pacman -S ydotool portaudio
```

Add the user to the `input` group (required for keyboard detection and ydotool):

```bash
sudo usermod -aG input $USER
```

They must log out and back in, or run `newgrp input` for the group to take effect.

Enable the ydotool service:

```bash
systemctl --user enable --now ydotool
```

Verify it works:

```bash
ydotool type "hello"
```

**macOS:**

No system dependencies needed beyond Python 3.13+. Accessibility permission is
required — it will be prompted after first run.

---

## Step 3: Install murmur

```bash
git clone https://github.com/ls1xt/murmur.git
cd murmur
uv sync
```

If `uv` is not installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`

Verify:

```bash
murmur --help
```

---

## Step 4: Get an AssemblyAI API key

New accounts get $50 in free credits — enough for thousands of sessions.
Direct the user to: https://www.assemblyai.com/

Once they have a key, set it:

```bash
murmur config --key transcriber.api_key --value THEIR_KEY_HERE
```

---

## Step 5: Start the daemon

```bash
murmur daemon start
```

To start at login:

```bash
murmur daemon enable
```

Check it's running:

```bash
murmur daemon status
```

---

## Step 6: Verify it works

1. Have the user focus any text input (editor, browser address bar, terminal)
2. Hold <kbd>F12</kbd>
3. Say "hello world"
4. Release — the text should appear

If nothing happens, proceed to the troubleshooting section below.

**macOS — Accessibility permission:**
If the hotkey is not detected, guide them to:
System Settings → Privacy & Security → Accessibility → add their terminal app.

---

## Troubleshooting

### "No keyboard devices found" (Linux)

```bash
groups | grep input   # should show "input"
sudo usermod -aG input $USER
# Log out and back in
```

### ydotool not working

```bash
systemctl --user status ydotool
systemctl --user enable --now ydotool
ydotool type "test"
```

### Characters dropped in editors

```bash
murmur config --key injector.key_delay --value 5
# Or switch to clipboard mode (pastes all at once):
murmur config --key injector.inject_strategy --value clipboard
```

### View logs

```bash
murmur daemon status
MURMUR_LOG_LEVEL=DEBUG murmur record   # single session with verbose output
```

---

## Optional: Custom vocabulary

If the user works with project-specific terms that speech recognition tends to
mangle (class names, CLI tools, abbreviations), boost accuracy with keyterms:

```bash
murmur config --key transcriber.keyterms --value "kubectl,PyTorch,MyClassName"
```

If the project has a `CLAUDE.md`, import keyterms from it automatically:

```bash
murmur keyterms import
```

---

## Optional: Select a microphone

```bash
murmur list-mics                                              # list with index
murmur config --key transcriber.mic_device --value 2         # select by index
murmur config --key transcriber.mic_device --value "Scarlett Solo"  # or by name
```

---

## Further reading

- Full configuration reference: [`docs/configuration.md`](docs/configuration.md)
- Example config: [`examples/config.json`](examples/config.json)
- Main README: [`README.md`](README.md)
