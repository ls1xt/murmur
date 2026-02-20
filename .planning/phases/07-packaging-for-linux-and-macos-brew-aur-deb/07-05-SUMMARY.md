---
plan: "07-05"
phase: "07"
status: complete
completed: 2026-02-20
---

# Plan 07-05: .deb Build Script and README Update

## What was built

### .deb packaging (packaging/deb/build-deb.sh)

Uses fpm to convert the Python wheel into a Debian package:
- Installs into `/opt/murmur` virtualenv with all deps bundled (including assemblyai and customtkinter, which are not in Debian repos)
- Creates `/usr/local/bin/murmur` wrapper that delegates to `/opt/murmur/bin/murmur`
- Post-install script guides user to `murmur config --key transcriber.api_key --value YOUR_KEY`
- Reads version from pyproject.toml at build time

### README.md

Rewrote README with proper structure for a released package:
- **Installation section** covering all four channels: Homebrew, AUR, .deb, PyPI (murmur-dictation)
- **First Run section** guiding user through `murmur config` and `murmur daemon start`
- **Usage section** showing all subcommands with inline comments
- **System Dependencies** for Linux setup
- **Configuration** section with dot-notation examples including keyterms

## Files created/modified

- packaging/deb/build-deb.sh — fpm-based .deb builder (executable)
- packaging/deb/README.md — build and install instructions
- README.md — complete rewrite with all install paths documented

## Self-Check: PASSED

- `bash -n packaging/deb/build-deb.sh` — syntax OK ✓
- `grep -c "brew install\|yay -S\|dpkg\|pip install" README.md` — 4 matches ✓
- `grep "murmur daemon" README.md` — subcommand usage documented ✓
- `wc -l README.md` — 171 lines ✓
- Post-install hook directs user to `murmur config` ✓

## key-files

### created
- packaging/deb/build-deb.sh
- packaging/deb/README.md

### modified
- README.md
