# Phase 7: Packaging for Linux and macOS (brew, AUR, deb) - Context

**Gathered:** 2026-02-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Distribute murmur through package managers (Homebrew, AUR, .deb, PyPI) so users can install it with a single command. This phase also includes designing the `murmur` CLI subcommand structure that the installed package exposes. No new core transcription or injection features.

</domain>

<decisions>
## Implementation Decisions

### Distribution channels
- Homebrew (macOS) — formula, not cask (build from source)
- AUR (Arch Linux) — PKGBUILD for `python-murmur` or `murmur`
- `.deb` (Debian/Ubuntu) — installable package
- PyPI (`pip install murmur`) — standard Python distribution
- No `.rpm` for now (not mentioned by user, not in phase scope)

### Homebrew formula
- Use Homebrew formula (source-based install), not cask
- Formula will depend on Python and declare pip dependencies
- Typical approach: formula installs into virtualenv via `pip install` from PyPI

### CLI subcommand structure
- Replace current single-entrypoint `main()` with subcommands:
  - `murmur config` — set/view configuration (API key, settings)
  - `murmur record` — single recording session (run once, transcribe, exit)
  - `murmur daemon` — manage background service (start, stop, status)
- This is a design change to `murmur/main.py` required for installability/UX

### Post-install setup and first-run UX
- If `murmur record` (or any command needing the API key) is run without a configured key, automatically prompt for it before proceeding — don't just fail with an error
- `murmur config` also available explicitly for setting/viewing config
- No interactive prompts at install time (works cleanly in CI and package managers)

### GUI config prompt
- Use **customtkinter** for a cross-platform GUI dialog when a terminal is not suitable or for a nicer UX
- GUI prompt collects:
  - AssemblyAI API key (required)
  - Custom vocabulary / keyterms (optional — comma-separated words to boost recognition accuracy)
- Triggered when API key is missing and a GUI is available; falls back to terminal prompt if no display
- This pulls UX-05 (custom keyterms) from v2 into this phase — planner should note this

### Service management
- `murmur daemon start/stop/status` handles service lifecycle
- Packages include systemd/launchd service files but do NOT auto-activate them
- User opts in to auto-start via `murmur daemon enable` or manual service registration

### Claude's Discretion
- Exact AUR package naming (`murmur` vs `python-murmur`)
- Config file format and location (`~/.config/murmur/config.toml` or similar)
- Whether `murmur daemon` wraps systemctl/launchctl or manages the process directly
- Whether to show GUI prompt always or only when no TTY is available

</decisions>

<specifics>
## Specific Ideas

- User explicitly wants the CLI to feel like a proper tool: config / record / daemon subcommands
- PyPI was confirmed as in scope alongside the native package manager targets
- Formula approach for Homebrew is preferred (source-based, no binary artifacts to maintain)
- customtkinter chosen for GUI dialog (modern look, cross-platform, one pip dep)
- GUI prompt should feel friendly, not like a config file — collect API key + optional keyterms in one shot

</specifics>

<deferred>
## Deferred Ideas

- `.rpm` packaging (Fedora/RHEL) — not in this phase, add to backlog if needed
- Auto-start on login by default (packages don't register services automatically)
- Windows support — out of scope for this project
- UX-05 (custom keyterms) moved from v2 into this phase — update REQUIREMENTS.md traceability during planning

</deferred>

---

*Phase: 07-packaging-for-linux-and-macos-brew-aur-deb*
*Context gathered: 2026-02-20*
