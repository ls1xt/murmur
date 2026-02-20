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

### Post-install setup
- Users run `murmur config` to provide their AssemblyAI API key
- No interactive prompts at install time (works cleanly in CI and package managers)

### Service management
- `murmur daemon start/stop/status` handles service lifecycle
- Packages include systemd/launchd service files but do NOT auto-activate them
- User opts in to auto-start via `murmur daemon enable` or manual service registration

### Claude's Discretion
- Exact AUR package naming (`murmur` vs `python-murmur`)
- Config file format and location (`~/.config/murmur/config.toml` or similar)
- Whether `murmur daemon` wraps systemctl/launchctl or manages the process directly

</decisions>

<specifics>
## Specific Ideas

- User explicitly wants the CLI to feel like a proper tool: config / record / daemon subcommands
- PyPI was confirmed as in scope alongside the native package manager targets
- Formula approach for Homebrew is preferred (source-based, no binary artifacts to maintain)

</specifics>

<deferred>
## Deferred Ideas

- `.rpm` packaging (Fedora/RHEL) — not in this phase, add to backlog if needed
- Auto-start on login by default (packages don't register services automatically)
- Windows support — out of scope for this project

</deferred>

---

*Phase: 07-packaging-for-linux-and-macos-brew-aur-deb*
*Context gathered: 2026-02-20*
