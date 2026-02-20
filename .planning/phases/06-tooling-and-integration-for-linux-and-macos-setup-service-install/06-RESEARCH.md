# Phase 6 Research: Tooling and Integration for Linux and macOS

**Phase:** 6 — setup, service, install
**Researched:** 2026-02-20

---

## What Exists Today

### Shell Scripts (all in repo root)

| File | Current State | Issues |
|------|---------------|--------|
| `setup.sh` | Linux-only. Detects distro (pacman/apt/dnf), installs ydotool+portaudio, checks input group, checks ydotoold, runs `uv sync` | No macOS branch |
| `install-service.sh` | Linux-only. Uses `sed` to substitute hardcoded string `%h/dev/python/murmur` with `$SCRIPT_DIR`, copies to `~/.config/systemd/user/`, runs `systemctl --user enable --now murmur` | Fragile sed substitution with hardcoded old path; no macOS branch |
| `run.sh` | Linux-only developer entrypoint. Checks venv, API key, sounddevice, input group, starts ydotoold if needed, silences ALSA/JACK stderr noise | No macOS branch; Linux-specific checks must be gated |
| `config-api-key.sh` | Platform-neutral already. Writes to `~/.config/murmur/config.json` | No changes needed |
| `murmur.service` | systemd user unit. `ExecStart=%h/dev/python/murmur/.venv/bin/murmur`. Documentation field has same hardcoded path. | Documentation line has hardcoded old path; ExecStart uses `%h` systemd variable (correct), but install-service.sh's sed approach is fragile |

### Service File Analysis

`murmur.service`:
```ini
[Unit]
Description=Murmur voice dictation daemon
Documentation=file://%h/dev/python/murmur/README.md   # BUG: hardcoded old path
After=graphical-session.target sound.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=%h/dev/python/murmur/.venv/bin/murmur        # uses %h (systemd expands to $HOME)
Restart=on-failure
RestartSec=3
Environment=PATH=/usr/local/bin:/usr/bin:/bin
PassEnvironment=DISPLAY WAYLAND_DISPLAY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS PULSE_SERVER

[Install]
WantedBy=graphical-session.target
```

The `%h` in systemd is correct — it expands to the user's home directory. The issue is that the path `/dev/python/murmur` is the developer's personal path. `install-service.sh` currently replaces the whole `%h/dev/python/murmur` string with `$SCRIPT_DIR`.

**Better approach**: Make the service file use a placeholder like `@@MURMUR_DIR@@` for the project root and `@@VENV_BIN@@` for the venv binary path. The install script then substitutes these cleanly.

---

## macOS LaunchAgent

### Structure

macOS LaunchAgents are plist XML files installed to `~/Library/LaunchAgents/`. The standard pattern:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.murmur.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/.venv/bin/murmur</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/murmur.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/murmur.log</string>
</dict>
</plist>
```

**Key semantics:**
- `RunAtLoad: true` — starts on login
- `KeepAlive.SuccessfulExit: false` — restart on crash (not on clean exit), equivalent to `Restart=on-failure` in systemd
- `Label` must be a reverse-DNS identifier
- Paths must be absolute (no `~` expansion in plists)

### launchctl commands

```bash
# Install and load
launchctl load ~/Library/LaunchAgents/com.murmur.daemon.plist

# Or on macOS 10.15+ (Catalina+):
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.murmur.daemon.plist

# Start/stop
launchctl start com.murmur.daemon
launchctl stop com.murmur.daemon

# Uninstall
launchctl unload ~/Library/LaunchAgents/com.murmur.daemon.plist
# or: launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.murmur.daemon.plist

# Status
launchctl list | grep murmur
```

**Recommendation**: Use `launchctl load` for broad compatibility (works on macOS 10.10+). The newer `bootstrap`/`bootout` commands work on Catalina+ but `load`/`unload` still function.

---

## macOS Homebrew Dependencies

For `setup.sh` macOS branch, the required Homebrew packages:

```bash
brew install portaudio
# pynput, pyobjc-framework-ApplicationServices — installed via pip/uv (in pyproject.toml), not brew
# uv itself — user should have it; can check and suggest install if missing
```

macOS does NOT need ydotool/ydotoold. The pynput injector uses `Controller.type()` and pbcopy.

**Check for Homebrew**: `command -v brew` — if missing, print install URL and exit.

**uv check**: `command -v uv` — if missing, print `curl -LsSf https://astral.sh/uv/install.sh | sh` and exit.

---

## run.sh macOS Branch

On macOS:
- **Skip**: ydotoold check, input group check, the ydotoold startup block
- **Skip**: ALSA/JACK stderr filtering (macOS uses CoreAudio, no ALSA noise)
- **Keep**: venv check, API key check, sounddevice check
- **Add**: (nothing — macOS Accessibility permissions are checked at runtime by `DictationApp.run()` in main.py, per Phase 05-04)

macOS stderr is clean from PortAudio (CoreAudio backend has no console noise), so the stderr filter pipeline can be omitted entirely on macOS.

**OS detection pattern for bash scripts:**
```bash
OS="$(uname -s)"
case "$OS" in
    Linux*)  # Linux path
    Darwin*) # macOS path
    *)       echo "Unsupported OS: $OS"; exit 1 ;;
esac
```

---

## Service File Template Strategy

**Recommended approach**: Use `@@PLACEHOLDER@@` tokens in the service/plist templates.

`murmur.service` (template):
```ini
ExecStart=@@MURMUR_DIR@@/.venv/bin/murmur
Documentation=file://@@MURMUR_DIR@@/README.md
```

`install-service.sh` on Linux:
```bash
sed "s|@@MURMUR_DIR@@|$SCRIPT_DIR|g" "$SCRIPT_DIR/murmur.service" > "$SERVICE_DIR/murmur.service"
```

`murmur.plist` (template):
```xml
<string>@@MURMUR_DIR@@/.venv/bin/murmur</string>
```

`install-service.sh` on macOS:
```bash
sed "s|@@MURMUR_DIR@@|$SCRIPT_DIR|g" "$SCRIPT_DIR/murmur.plist" > "$PLIST_DIR/com.murmur.daemon.plist"
launchctl load "$PLIST_DIR/com.murmur.daemon.plist"
```

This is cleaner than the current approach because:
1. The placeholder is explicit and won't accidentally match other parts of the file
2. One `sed` call handles all occurrences
3. No dependency on knowing the old hardcoded path

---

## Plan Decomposition

Based on the CONTEXT.md decisions and what exists, the work decomposes into:

### Plan 1: Fix service file and install-service.sh (Linux side)
- Fix `murmur.service` — replace hardcoded Documentation path with `@@MURMUR_DIR@@` placeholder, replace ExecStart `%h/dev/python/murmur` with `@@MURMUR_DIR@@`
- Fix `install-service.sh` — replace fragile `sed "s|%h/dev/python/murmur|$SCRIPT_DIR|g"` with clean placeholder substitution using `@@MURMUR_DIR@@`
- Verify: service installs and starts cleanly on Linux

### Plan 2: setup.sh macOS branch
- Add macOS detection to `setup.sh`
- macOS branch: check for `brew`, install `portaudio` via brew, skip ydotool (not available/needed on macOS), skip input group check, run `uv sync`, print macOS-specific next steps
- Linux branch: unchanged logic (just moved into the `Linux*` case)
- Verify: script runs without error on macOS (at least dry-run / logic check)

### Plan 3: run.sh macOS branch
- Add OS detection to `run.sh`
- Linux path: current logic unchanged
- macOS path: venv check, API key check, sounddevice check (same as Linux), skip ydotoold, skip input group, skip ALSA/JACK stderr filter, run murmur directly
- Verify: script runs on macOS without ydotoold-related errors

### Plan 4: murmur.plist + macOS install-service.sh branch
- Create `murmur.plist` LaunchAgent template with `@@MURMUR_DIR@@` placeholder
- Add macOS branch to `install-service.sh`: substitute placeholder, copy to `~/Library/LaunchAgents/com.murmur.daemon.plist`, run `launchctl load`
- Add status/logs/stop instructions echo matching Linux UX
- Verify: plist structure is valid, install path correct

**Alternative consolidation**: Plans 1+4 could be combined (both touch install-service.sh). Plans 2+3 could be combined (both touch setup.sh and run.sh). This yields 2 larger plans or 4 focused ones.

**Recommendation**: 3 plans:
1. `06-01-PLAN.md` — Fix murmur.service + install-service.sh (Linux service + template approach)
2. `06-02-PLAN.md` — Create murmur.plist + add macOS branch to install-service.sh
3. `06-03-PLAN.md` — Add macOS branches to setup.sh and run.sh

Plans 1 and 2 both touch install-service.sh so they should be wave 1 (sequential) or merged. Actually plan 1 fixes the Linux path and introduces the placeholder approach, plan 2 adds the macOS path. They'd conflict if parallel. Better: merge into 2 plans:

1. `06-01-PLAN.md` — Refactor service tooling: fix murmur.service template + overhaul install-service.sh (Linux fix + macOS branch + murmur.plist creation) [wave 1]
2. `06-02-PLAN.md` — Cross-platform setup.sh and run.sh: add macOS branches to both [wave 1, parallel with 01 if files don't overlap — they don't]

Actually setup.sh and run.sh don't overlap with install-service.sh and murmur.service/murmur.plist, so both plans can run in **wave 1 in parallel**.

---

## Verification Criteria for Phase

After Phase 6 is complete:
1. `./setup.sh` on macOS detects Darwin, installs portaudio via brew, runs `uv sync`
2. `./setup.sh` on Linux works as before (no regression)
3. `./install-service.sh` on Linux installs service using dynamic path (no hardcoded paths)
4. `./install-service.sh` on macOS installs LaunchAgent to `~/Library/LaunchAgents/`
5. `murmur.service` has no hardcoded paths — uses `@@MURMUR_DIR@@` placeholders
6. `murmur.plist` exists with proper LaunchAgent structure and `@@MURMUR_DIR@@` placeholder
7. `./run.sh` on macOS skips ydotoold/input group checks, runs murmur directly
8. `./run.sh` on Linux works as before (no regression)

---

## RESEARCH COMPLETE

Phase 6 is a focused shell scripting phase: fix the existing Linux tooling fragilities and add macOS branches. No Python changes required. Two plans running in parallel (wave 1) cover all the work cleanly.
