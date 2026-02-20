---
plan: "07-04"
phase: "07"
status: complete
completed: 2026-02-20
---

# Plan 07-04: Homebrew Formula and AUR PKGBUILD

## What was built

Packaging artifacts for macOS (Homebrew) and Arch Linux (AUR) installation.

### Homebrew formula (packaging/homebrew/murmur.rb)

- Uses `Language::Python::Virtualenv` mixin — standard Homebrew pattern for Python packages
- Declares `portaudio` and `python@3.11` as system dependencies
- Declares all 7 Python deps as resource blocks with placeholder sha256 values
- URL points to PyPI sdist once murmur-dictation is published
- Includes `test do` block calling `murmur --help`

### AUR PKGBUILD (packaging/aur/PKGBUILD)

- Named `python-murmur` (Arch naming convention for Python packages; avoids conflict with Mumble server "murmur")
- Declares system deps: python-pillow, python-pystray, python-sounddevice, portaudio
- Build step uses `python -m build --wheel --no-isolation`
- Install step uses `python -m installer --destdir="$pkgdir"`
- Post-install hook: `python-murmur.install` directs user to `murmur config` and systemctl

### Companion files

- `packaging/aur/.SRCINFO` — static AUR metadata companion
- `packaging/aur/README.md` — AUR publish instructions
- `packaging/homebrew/README.md` — Homebrew tap setup instructions

## Files created

- packaging/homebrew/murmur.rb
- packaging/homebrew/README.md
- packaging/aur/PKGBUILD
- packaging/aur/.SRCINFO
- packaging/aur/python-murmur.install
- packaging/aur/README.md

## Self-Check: PASSED

- `bash -n packaging/aur/PKGBUILD` — syntax OK ✓
- `grep "pkgname=python-murmur" packaging/aur/PKGBUILD` — correct name ✓
- `grep "python -m build" packaging/aur/PKGBUILD` — build step present ✓
- `grep "Language::Python::Virtualenv" packaging/homebrew/murmur.rb` — present ✓
- `grep "portaudio" packaging/homebrew/murmur.rb` — present ✓
- `grep -c "resource" packaging/homebrew/murmur.rb` — 8 (7 resource blocks + comment) ✓

## key-files

### created
- packaging/homebrew/murmur.rb
- packaging/aur/PKGBUILD
- packaging/aur/.SRCINFO
