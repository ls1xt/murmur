# Phase 6: Tooling and Integration for Linux and macOS - Context

**Gathered:** 2026-02-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver working setup, service install, and dev-run tooling for both Linux and macOS — so a user can clone the repo, run one script, and have Murmur running. Covers: unified setup script, systemd service (Linux) and LaunchAgent (macOS), a single service-install script that branches by platform, and a dev-friendly `run.sh` that works on both OSes. Does NOT include packaging (brew formula, AUR, .deb, etc.) — that is a separate future phase.

</domain>

<decisions>
## Implementation Decisions

### Script structure
- Single `setup.sh` that detects the OS and branches internally
  - Linux branch: existing distro detection (pacman/apt/dnf) + system deps (ydotool, portaudio)
  - macOS branch: Homebrew deps (portaudio, pynput requirements, etc.)
- Single `install-service.sh` that detects OS and runs the appropriate install path
  - Linux: installs systemd user service (fix the current hardcoded `sed` path hack — use dynamic `$SCRIPT_DIR` throughout)
  - macOS: installs a LaunchAgent plist to `~/Library/LaunchAgents/`

### macOS auto-start (LaunchAgent)
- Provide a `murmur.plist` LaunchAgent template alongside `murmur.service`
- `install-service.sh` on macOS: substitutes the real path into the plist, copies to `~/Library/LaunchAgents/`, and runs `launchctl load` to start it immediately
- Match the same UX as the Linux path: one command installs and starts the service

### Service file / plist fixes
- Fix the hardcoded `%h/dev/python/murmur` path in `murmur.service` Documentation field
- Fix `install-service.sh`'s fragile `sed` substitution — use `$SCRIPT_DIR` consistently, no hardcoded paths anywhere

### run.sh (developer entrypoint)
- `run.sh` is for developers testing local changes, not end users
- Must work on both Linux and macOS
- Linux: keeps existing checks (ydotoold running, input group membership)
- macOS: skips ydotoold/input group checks (macOS uses Accessibility permissions, which are handled at runtime by `DictationApp.run()` already)
- OS detection determines which preflight checks to run

### Claude's Discretion
- Exact Homebrew formula names for macOS deps
- LaunchAgent plist structure and keep-alive semantics
- Whether to merge `config-api-key.sh` into setup.sh or keep it separate

</decisions>

<specifics>
## Specific Ideas

- After phase 6, packaging (brew formula, AUR, .deb) becomes a natural follow-on — phase 6 gets the manual install story solid first
- The `run.sh` ALSA/JACK stderr-filter block is Linux-specific; macOS may need its own stderr suppression or none at all

</specifics>

<deferred>
## Deferred Ideas

- Homebrew formula / AUR package / .deb packaging — future phase (DIST-01, DIST-02, DIST-03 from v2 requirements)
- One-line install script (DIST-03) — depends on packaging existing first

</deferred>

---

*Phase: 06-tooling-and-integration-for-linux-and-macos-setup-service-install*
*Context gathered: 2026-02-20*
