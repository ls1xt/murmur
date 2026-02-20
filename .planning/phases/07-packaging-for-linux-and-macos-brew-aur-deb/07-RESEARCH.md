# Phase 7 Research: Packaging for Linux and macOS (brew, AUR, deb)

**Phase:** 7 — packaging and distribution
**Researched:** 2026-02-20

---

## What Exists Today

### Python Package

`pyproject.toml` uses **hatchling** as the build backend. Key facts:
- `name = "murmur"` — PyPI package name
- `version = "0.1.0"`
- `[project.scripts] murmur = "murmur.main:main"` — single entry point, no subcommands
- Platform-conditional deps: `evdev` Linux-only, `pynput`/`pyobjc` Darwin-only
- Build-system: `hatchling` (not setuptools)
- `uv.lock` present — project uses `uv` for development

### CLI Entry Point (murmur/main.py)

Current `main()` is a flat argparse function. No subcommands. The CONTEXT.md decision is to refactor to:
- `murmur config` — set/view config (API key, settings)
- `murmur record` — single recording session (run once, transcribe, exit)
- `murmur daemon` — manage background service (start, stop, status)

This is **required** for the package to feel like a proper tool.

### Config System (murmur/config.py)

- Config location: `~/.config/murmur/config.json`
- Loaded via `DictationConfig.load()` — reads JSON + env var overrides
- `DictationConfig.save()` — writes to config file
- API key stored under `transcriber.api_key` in JSON, or env `ASSEMBLYAI_API_KEY`

### Service Files (from Phase 6)

- `murmur.service` — systemd user unit, `@@MURMUR_DIR@@` placeholder
- `murmur.plist` — macOS LaunchAgent, `@@MURMUR_DIR@@` placeholder
- `install-service.sh` — OS-detecting installer (Linux: systemctl, macOS: launchctl)

---

## Distribution Channel Requirements

### PyPI (pip install murmur)

**What's needed:**
1. `pyproject.toml` already has all required fields for PyPI upload
2. Build with `hatch build` or `python -m build` → produces wheel + sdist in `dist/`
3. Upload: `twine upload dist/*` (or `uv publish`)
4. **Name conflict risk**: "murmur" is likely taken on PyPI — check first; may need `murmur-dictation` or `murmur-voice`

**PyPI-specific requirements:**
- `license` field format: `{text = "MIT"}` is correct for hatchling
- `readme = "README.md"` is correct
- `description` is short enough (one line)
- Missing for PyPI: `authors`, `keywords`, `classifiers`, `urls` — these should be added
- hatchling requires `HATCH_BUILD_CLEAN=true` or similar if using custom hooks

**Wheel contents check:**
- hatchling auto-discovers the `murmur/` package
- Platform-specific files (service files, shell scripts) should NOT be in the wheel
- Only Python source goes in the wheel; scripts go in `[project.scripts]`

**Platform markers are correct** for conditional deps.

### Homebrew Formula

**Formula type**: Source formula (not cask — builds from source)

**Typical pattern for Python packages in Homebrew:**
```ruby
class Murmur < Formula
  include Language::Python::Virtualenv

  desc "System-wide voice dictation for Linux and macOS"
  homepage "https://github.com/..."
  url "https://files.pythonhosted.org/packages/.../murmur-0.1.0.tar.gz"
  sha256 "..."
  license "MIT"

  depends_on "python@3.11"
  depends_on "portaudio"

  # Declare Python deps as resources
  resource "assemblyai" do
    url "https://..."
    sha256 "..."
  end
  # ... more resources

  def install
    virtualenv_install_with_resources
  end
end
```

**Key facts about Homebrew Python formulas:**
- Use `Language::Python::Virtualenv` mixin
- `virtualenv_install_with_resources` creates a venv, installs all resources, then installs the package
- Each pip dependency must be declared as a `resource` block with a URL and sha256
- Homebrew does NOT use `pip install -r requirements.txt`; every dep is explicit
- The formula lives in a tap (e.g., `homebrew/core` or a personal tap like `user/murmur`)
- To get into homebrew/core, you need: stable URL, all deps declared, formula review
- **Practical first step**: Personal tap (`brew tap user/murmur && brew install murmur`)

**Generating resource blocks**: `brew formula murmur` can auto-generate from a PyPI package once it's published; or use `pip2formula`/`homebrew-pypi-poet` tooling

**murmur-specific**: `portaudio` is a required system dep. `pynput` and `pyobjc` are macOS-only. Homebrew formulas can use `:if_os :macos` conditionals for platform-specific resources.

### AUR (Arch Linux)

**Two standard AUR package types:**
1. `murmur` — builds from source (PKGBUILD with `makedepends`, `build()`, `package()`)
2. `python-murmur` — naming convention for Python packages on AUR; installs to system Python

**PKGBUILD structure:**
```bash
pkgname=python-murmur
pkgver=0.1.0
pkgrel=1
pkgdesc="System-wide voice dictation for Linux and macOS"
arch=('x86_64')
url="https://github.com/..."
license=('MIT')
depends=('python' 'python-assemblyai' 'python-evdev' 'python-pystray' 'python-pillow' 'python-sounddevice' 'portaudio')
makedepends=('python-build' 'python-installer' 'python-wheel' 'python-hatchling')
source=("https://files.pythonhosted.org/packages/.../murmur-${pkgver}.tar.gz")
sha256sums=('...')

build() {
    cd "murmur-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "murmur-${pkgver}"
    python -m installer --destdir="$pkgdir" dist/*.whl
}
```

**AUR naming decision**: Use `python-murmur` (conventional for Python packages). AUR package `murmur` may conflict with the existing `murmur` (Mumble server) AUR package — check.

**AUR publishing**: Create `PKGBUILD` + `.SRCINFO` (generated via `makepkg --printsrcinfo > .SRCINFO`), push to AUR Git.

### .deb Package (Debian/Ubuntu)

**Two approaches:**
1. **`fpm` (effing package manager)**: Simple one-command deb creation from a Python wheel
2. **`debhelper`/`dh_python3`**: The "proper" Debian way — complex but native

**fpm approach** (recommended for first release):
```bash
pip install fpm  # or gem install fpm
fpm -s python -t deb --python-bin python3 --no-python-dependencies \
    --depends python3 --depends python3-assemblyai \
    murmur-0.1.0.tar.gz
```

**Or using wheel:**
```bash
# Build wheel first
python -m build
# Convert to deb
fpm -s dir -t deb -n murmur -v 0.1.0 \
    --prefix /usr/local \
    .venv/lib/python3.x/site-packages/murmur=/usr/lib/python3/dist-packages/murmur \
    .venv/bin/murmur=/usr/local/bin/murmur
```

**`stdeb` approach** (simpler, purpose-built for Python → deb):
```bash
pip install stdeb
python setup.py --command-packages=stdeb.command bdist_deb
# Or for pyproject.toml:
pyproject-to-distutils && python setup.py --command-packages=stdeb.command bdist_deb
```

**Practical recommendation**: Use `python-stdeb` or `fpm`. Native debhelper is complex.

**Debian package considerations:**
- Deps: `python3-evdev`, `python3-pillow`, `python3-sounddevice`, `ydotool`, `portaudio19-dev`
- Some deps (`assemblyai`, `pystray`) are NOT in Debian repos — must bundle or require PyPI
- For a simple initial release: recommend `pip install murmur` on Debian/Ubuntu, or use fpm to bundle a venv

---

## CLI Subcommand Refactor (murmur/main.py)

### Current State
`main()` is a single argparse function that directly starts the daemon. No subcommands.

### Required Design (from CONTEXT.md)

```
murmur config [--key KEY] [--value VALUE]  # get/set config values
murmur record                               # single session (run, transcribe, exit)
murmur daemon {start|stop|status|enable}    # service management
```

**Implementation using argparse subparsers:**

```python
def main() -> None:
    parser = argparse.ArgumentParser(description="Murmur voice dictation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # murmur config
    config_parser = subparsers.add_parser("config", help="View/set configuration")
    config_parser.add_argument("--key", help="Config key (e.g. transcriber.api_key)")
    config_parser.add_argument("--value", help="Value to set")

    # murmur record
    record_parser = subparsers.add_parser("record", help="Single dictation session")
    # ... flags

    # murmur daemon
    daemon_parser = subparsers.add_parser("daemon", help="Manage background service")
    daemon_parser.add_argument("action", choices=["start", "stop", "status", "enable"])
```

**`murmur config` behavior:**
- No args: print current config (from `~/.config/murmur/config.json`)
- `--key transcriber.api_key --value xxx`: set the value, save config
- Special case: `murmur config --key transcriber.api_key --value $KEY` replaces the existing `config-api-key.sh` shell script

**`murmur record` behavior:**
- Essentially the current daemon behavior but exits after one complete dictation session
- Useful for scripting: `echo "$(murmur record)"` waits and exits

**`murmur daemon` behavior:**
- `start`: launch daemon in background (or start systemd/launchd service if installed)
- `stop`: stop the daemon (send SIGTERM or stop service)
- `status`: show whether daemon is running
- `enable`: call `install-service.sh` logic directly

**Test impact**: `test_main.py` tests currently call `main()` directly — refactoring to subcommands will break existing tests. New tests needed for each subcommand.

### Backward Compatibility

The current `murmur` entry point starts the daemon directly (current behavior = future `murmur daemon start` or just run directly). After refactoring, `murmur` with no args should show help or error, not silently start the daemon.

**Migration path**: Keep `DictationApp.run()` as-is; the `murmur daemon start` subcommand calls it in the foreground (or in background via subprocess).

---

## pyproject.toml Additions Needed

For PyPI publish:
```toml
[project]
authors = [{name = "Leon", email = "..."}]
keywords = ["voice", "dictation", "speech-to-text", "accessibility"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: No Input/Output (Daemon)",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Operating System :: POSIX :: Linux",
    "Operating System :: MacOS",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Utilities",
]

[project.urls]
Homepage = "https://github.com/..."
Repository = "https://github.com/..."
Issues = "https://github.com/..."
```

---

## Package Manager Artifacts to Create

| Artifact | Location in Repo | Notes |
|----------|-----------------|-------|
| `PKGBUILD` | `packaging/aur/PKGBUILD` | AUR build script |
| `.SRCINFO` | `packaging/aur/.SRCINFO` | Generated from PKGBUILD |
| `Formula/murmur.rb` | `packaging/homebrew/murmur.rb` | Homebrew formula |
| `packaging/deb/` | `packaging/deb/` | fpm script or stdeb config |

Or alternatively, keep them at repo root if single-level structure is preferred.

---

## Packaging Sequencing / Plan Decomposition

Based on the CONTEXT.md decisions and complexity analysis:

### Plan 1: CLI Subcommand Refactor (murmur/main.py)
**Required before packaging** — `murmur config` must exist for the install UX to work.
- Refactor `main()` to use argparse subparsers
- Implement `murmur config` (view/set config values including API key)
- Implement `murmur daemon` (start/stop/status wrapping service commands)
- Keep `murmur record` as a documented stub or simple one-shot mode
- Update `pyproject.toml` entry point (no change needed — still `murmur.main:main`)
- Update `test_main.py` to cover new subcommand structure
- Remove `config-api-key.sh` (replaced by `murmur config`)

### Plan 2: PyPI Packaging
- Add `authors`, `keywords`, `classifiers`, `urls` to `pyproject.toml`
- Add `[build-system]` `build` and `twine` to dev dependencies
- Write `Makefile` or `scripts/publish.sh` with: `uv build && uv publish` workflow
- Document `PYPI_TOKEN` usage (don't hardcode)
- Verify package name isn't taken; if "murmur" is taken use "murmur-dictation"
- Verify wheel contents (no service files, no .sh scripts in the wheel)
- Add `.pypirc` to `.gitignore`

### Plan 3: Homebrew Formula
- Create `packaging/homebrew/murmur.rb` formula
- Use `Language::Python::Virtualenv` pattern
- Declare `portaudio` as system dep
- Declare Python deps as resources (assemblyai, pystray, pillow, sounddevice, pynput, pyobjc-framework-ApplicationServices)
- Write `brew tap` instructions in README
- Note: formula must reference a stable PyPI URL — do Plan 2 first

### Plan 4: AUR PKGBUILD
- Create `packaging/aur/PKGBUILD` for `python-murmur`
- Verify no name conflict with Mumble server's `murmur` AUR package
- Add `murmur.service`, `murmur.install` hooks for post-install instructions
- Generate `.SRCINFO`
- Write AUR submission instructions

### Plan 5: .deb Package
- Choose approach: `fpm` script (simplest) or `stdeb` config
- Create `packaging/deb/build-deb.sh` — builds the deb via fpm
- Dep mapping: assemblyai not in Debian repos → must use pip-installed venv approach or `pip install murmur` in the deb postinst
- Add GitHub Actions workflow stub for building release artifacts (deb + wheel)

---

## Wave Structure

**Wave 1 (blocker)**: Plan 1 — CLI refactor (all other plans depend on the new CLI being in place)

**Wave 2 (parallel)**: Plans 2, 3, 4, 5 — packaging artifacts (can all be written in parallel once PyPI exists; Plans 3/4/5 can be written before PyPI since they're just files)

**Practical wave structure:**
- Wave 1: Plan 1 (CLI refactor) — Python code changes
- Wave 2: Plan 2 (PyPI) — pyproject.toml + publish tooling
- Wave 3: Plans 3 + 4 + 5 in parallel — Homebrew + AUR + deb (all are just text files)

Alternatively, since plans 3/4/5 are just packaging artifact files with no code dependencies:
- Wave 1: Plan 1 (CLI refactor) + Plan 2 (PyPI additions to pyproject.toml) — both touch Python
- Wave 2: Plans 3 + 4 + 5 (pure packaging files, parallel)

---

## Verification Criteria

After Phase 7 is complete:
1. `murmur config` prints current config; `murmur config --key transcriber.api_key --value xxx` saves it
2. `murmur daemon start` starts the daemon (foreground) or wraps service command
3. `murmur daemon status` reports running/not running
4. `pip install murmur` (from PyPI) works; `murmur config` then `murmur daemon start` starts the tool
5. `brew install user/murmur/murmur` works (Homebrew tap)
6. `yay -S python-murmur` works (AUR) on Arch Linux
7. Installing the `.deb` and running `murmur daemon start` works on Ubuntu

---

## Key Risks and Decisions

| Risk | Decision |
|------|----------|
| PyPI name conflict ("murmur" taken) | Check; fallback to "murmur-dictation" |
| `assemblyai` not in Debian/Arch repos | Must declare as PyPI resource in Homebrew; declare in AUR makedepends via pip or AUR dep |
| `python-assemblyai` may not exist in AUR | May need to create `python-assemblyai` PKGBUILD too, or document pip install |
| Homebrew formula complexity (many resources) | Use `homebrew-pypi-poet` to auto-generate resource blocks |
| `murmur daemon` wraps systemctl/launchctl vs direct process mgmt | Wrap service commands (simpler, no PID file needed) |
| test_main.py must be updated | New tests for each subcommand |

---

## RESEARCH COMPLETE

Phase 7 has five plans:
1. CLI subcommand refactor (main.py) — Python changes, wave 1
2. PyPI packaging (pyproject.toml + publish tooling) — wave 1 or 2
3. Homebrew formula — wave 2 (parallel)
4. AUR PKGBUILD — wave 2 (parallel)
5. .deb packaging — wave 2 (parallel)

The CLI refactor is the primary Python work. All packaging artifacts are text-only files that can be created in parallel once the CLI shape is known.
