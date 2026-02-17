# Stack Research

**Domain:** System-wide voice dictation daemon (Linux/Wayland-first, macOS secondary)
**Researched:** 2026-02-17
**Confidence:** HIGH (all library versions verified against PyPI JSON API; behavior notes verified against official docs and GitHub issues)

---

## Recommended Stack

### Core Runtime

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.10+ | Runtime | Project already targets 3.10+. `match` statements, `X \| Y` union types, and `ParamSpec` all available. 3.12/3.13 preferred for faster startup. |
| uv | 0.10.3 | Package manager + venv | Replaces pip + virtualenv + pip-tools in one tool. 10-100x faster than pip. Manages `pyproject.toml` dependencies, lockfiles, and virtual envs. Standard in 2025/2026 Python projects. |

### Core Libraries (existing, keep)

| Library | Current Version | Purpose | Notes |
|---------|----------------|---------|-------|
| assemblyai | 0.52.0 | STT streaming via Universal-Streaming v3 | Actively maintained. `assemblyai.streaming.v3` module is stable. `StreamingClient`, `TurnEvent`, `BeginEvent` APIs used in prototype are correct. |
| evdev | 1.9.3 | Wayland-native hotkey detection via `/dev/input` | Actively maintained (1.9.3 released 2026-02-05). The only correct approach for system-wide hotkey detection on Wayland. Requires `input` group. |
| pynput | 1.8.1 | macOS hotkey detection + text injection | Version 1.8.1 released 2025-03-17. Keep for macOS secondary path only. **Do not use for Wayland hotkey detection** — confirmed broken on Wayland (reads only XWayland events). |
| PyAudio | 0.2.14 | Microphone capture (PCM16, 16kHz) | Last released 2023-11-07. Low maintenance velocity but stable — PortAudio itself is mature. AssemblyAI SDK's `MicrophoneStream` uses PyAudio internally; replacing PyAudio would require replacing that helper too. Keep for now. |

### Supporting Libraries (add)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| desktop-notifier | 6.2.0 | Desktop notifications (errors, status) | Linux: uses `org.freedesktop.Notifications` D-Bus — works on all Wayland compositors that run a notification daemon. macOS: uses Notification Center natively. No libnotify binary required. |
| pystray | 0.19.5 | System tray icon | **Use with AppIndicator backend only on Linux.** Requires `gir1.2-ayatana-appindicator3` (or `gir1.2-appindicator3`). Works on GNOME (with AppIndicator Shell Extension), KDE Plasma, and most non-GNOME desktops. Does NOT work on stock GNOME/Wayland without the extension. Requires `Pillow` for icon images. |
| Pillow | 11.x (latest) | Icon image creation for pystray | Required by pystray. Use to generate PNG/ICO tray icons from raw pixels. |

### Development Tools

| Tool | Version | Purpose | Configuration |
|------|---------|---------|---------------|
| Ruff | 0.15.1 | Linting + formatting | Replaces Black + isort + Flake8. Configure in `pyproject.toml` under `[tool.ruff]`. Enable ruleset `E, W, F, I, UP, B, C4`. |
| Pyright | 1.1.408 | Static type checking (strict mode) | Use `typeCheckingMode = "strict"` in `pyrightconfig.json` or `pyproject.toml [tool.pyright]`. Every ABC method, factory return type, and callback type must be annotated. |
| pytest | 9.0.2 | Test runner | Configure under `[tool.pytest.ini_options]` in `pyproject.toml`. |
| pytest-mock | 3.15.1 | Mocking for unit tests | Use `mocker.patch` to mock evdev devices, ydotool subprocess calls, and AssemblyAI SDK. Avoids real hardware in CI. |
| pytest-cov | 7.0.0 | Coverage reporting | Target 80%+ coverage on non-hardware paths. Hardware paths (evdev read loop, ydotool subprocess) are integration-only. |

---

## Installation

```bash
# Install uv (if not present)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Initialize pyproject.toml
uv init --lib murmur

# Core runtime deps
uv add assemblyai evdev pynput pyaudio desktop-notifier pystray Pillow

# Dev deps
uv add --dev ruff pyright pytest pytest-mock pytest-cov

# Optional: sounddevice (if replacing PyAudio later)
# uv add sounddevice
```

**System packages required (Debian/Ubuntu):**
```bash
sudo apt install portaudio19-dev gir1.2-ayatana-appindicator3-0.1 python3-gi libgirepository1.0-dev
```

**System packages required (Arch/Fedora):**
```bash
# Arch:
sudo pacman -S portaudio libayatana-appindicator python-gobject gobject-introspection
# Fedora:
sudo dnf install portaudio-devel libayatana-appindicator3 python3-gobject gobject-introspection
```

---

## Alternatives Considered

| Category | Recommended | Alternative | When to Use Alternative |
|----------|-------------|-------------|-------------------------|
| Package manager | uv | pip + venv | Never — uv is a strict superset |
| Hotkey (Wayland) | evdev | pynput | Never on Wayland; pynput is broken (GitHub #628, confirmed Feb 2025) |
| Text injection (Wayland) | ydotool | wtype | Only if targeting exclusively wlroots compositors (Sway, Hyprland). ydotool works everywhere (GNOME, KDE, wlroots) via uinput. |
| Text injection (Wayland) | ydotool | dotool | dotool is an ydotool-inspired Go binary — simpler but less widely packaged; no advantage over ydotool for this use case |
| Microphone | PyAudio | sounddevice | Consider sounddevice in a future refactor if PyAudio shows install friction; it uses the same PortAudio backend, has better API, and was last updated 2026-01-23. AssemblyAI SDK's `MicrophoneStream` uses PyAudio internally, so switching requires custom mic capture code. |
| STT | AssemblyAI SDK | OpenAI Whisper (local) | Future Phase 3: offline mode. faster-whisper (GPU/CPU GGML) is the recommended local alternative. |
| Tray icon | pystray + AppIndicator | Qt/GTK tray directly | Qt/GTK are large dependencies. pystray is lighter but still requires gobject-introspection on Linux. |
| Notifications | desktop-notifier | notify_py | desktop-notifier has async API, works on macOS via Notification Center natively (notify_py uses osascript). desktop-notifier is more actively maintained (v6.2.0 vs notify_py's last release in 2022). |
| Formatter/linter | Ruff | Black + isort + Flake8 | Never — Ruff replaces all three with 10-100x better performance |
| Type checker | Pyright | mypy | Pyright is significantly faster on large codebases, has better VSCode integration (Pylance), and strict mode is more precise than mypy's strict. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| pynput (Wayland hotkey listener) | Falls back to XWayland — only receives events from XWayland apps, not native Wayland apps. Confirmed broken in 2025 (GitHub #628). Wrong keyboard layout injected on non-US layouts. | evdev on Linux |
| xdotool | X11-only. Does not work under Wayland at all. | ydotool |
| wtype | wlroots-only. Does not work on GNOME Wayland or KDE Plasma by default. | ydotool |
| GTK.StatusIcon | Deprecated since GTK 3.14, removed in GTK4. Doesn't work on Wayland. | pystray + AppIndicator |
| PyAudio (without PortAudio headers) | Requires system-level `portaudio19-dev` build dependency. Users forget this and get cryptic pip failures. | Document the system dep clearly; consider sounddevice in future (same dep, same issue) |
| mypy | Slower than Pyright for incremental checks; worse IDE integration. The `assemblyai` SDK ships `py.typed` marker so Pyright can fully type-check SDK usage. | Pyright |
| Black + isort separately | Superseded by Ruff which does both faster | Ruff |
| notify-send subprocess | Shell-out is brittle; doesn't work if libnotify-bin not installed; no Python-native error handling. | desktop-notifier (D-Bus direct) |

---

## Stack Patterns by Variant

**If running on Wayland (GNOME with AppIndicator Shell Extension):**
- pystray with AppIndicator backend works
- evdev for hotkeys (required, no fallback)
- ydotool for injection (required, daemon must be running)

**If running on Wayland without AppIndicator support (e.g., bare GNOME without extension):**
- Tray icon will silently fail; handle gracefully — fall back to notifications-only mode
- desktop-notifier still works (D-Bus notifications are independent of tray)

**If running on macOS:**
- pynput for hotkeys (Accessibility permission required)
- pynput for text injection (same permission)
- desktop-notifier uses macOS Notification Center (signed binary or Terminal approval required)
- pystray with AppKit backend (works on macOS, no extension needed)

**If building for offline/local STT (Phase 3):**
- Add: `faster-whisper` (GPU-accelerated GGML Whisper)
- Add: `sounddevice` (modern PyAudio replacement for custom mic stream)
- The `Transcriber` ABC already accommodates this — no architecture change needed

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| assemblyai 0.52.0 | Python 3.8-3.14 | `assemblyai.streaming.v3` module stable; `MicrophoneStream` internally uses PyAudio |
| evdev 1.9.3 | Python 3.9+ | Requires Python 3.9+ (dropped 3.8); uses `py.typed` marker |
| PyAudio 0.2.14 | Python 3.8-3.12 | No wheel for Python 3.13+ as of 2026-02; build from source with portaudio19-dev |
| pystray 0.19.5 | Python 3+ | Requires Pillow; AppIndicator backend requires `gir1.2-appindicator3` or `gir1.2-ayatana-appindicator3` system package |
| desktop-notifier 6.2.0 | Python 3.9+ | Linux: requires dbus-next (pure Python); no system lib required beyond a running notification daemon (dunst, mako, etc.) |
| Pyright 1.1.408 | Python 3.10+ analysis | Specify `pythonVersion = "3.10"` in pyrightconfig.json to match minimum target |
| pytest 9.0.2 | Python 3.10+ | Requires Python >=3.10 to run |

**Critical compatibility note:** PyAudio 0.2.14 has no pre-built wheel for Python 3.13+. If targeting 3.13+, either pin to 3.10-3.12 or plan to replace PyAudio with sounddevice in a future refactor. The `assemblyai` SDK's `MicrophoneStream` helper wraps PyAudio — if PyAudio is replaced, a custom mic capture class using sounddevice must be written.

---

## pyproject.toml Skeleton

```toml
[project]
name = "murmur"
version = "0.1.0"
description = "System-wide voice dictation — hold a hotkey, speak, release"
requires-python = ">=3.10"
dependencies = [
    "assemblyai>=0.52.0",
    "evdev>=1.9.3",
    "pynput>=1.8.1",
    "PyAudio>=0.2.14",
    "desktop-notifier>=6.2.0",
    "pystray>=0.19.5",
    "Pillow>=10.0",
]

[project.scripts]
murmur = "murmur.__main__:main"

[project.optional-dependencies]
local-stt = ["faster-whisper>=1.0", "sounddevice>=0.5.5"]

[dependency-groups]
dev = [
    "ruff>=0.15.1",
    "pyright>=1.1.408",
    "pytest>=9.0.2",
    "pytest-mock>=3.15.1",
    "pytest-cov>=7.0.0",
]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "B", "C4", "RUF"]

[tool.pyright]
pythonVersion = "3.10"
typeCheckingMode = "strict"
include = ["murmur"]
exclude = ["tests"]   # relax strict for tests if needed

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=murmur --cov-report=term-missing"
```

---

## Sources

- PyPI JSON API `https://pypi.org/pypi/{package}/json` — version numbers verified 2026-02-17 (HIGH confidence)
- `https://github.com/moses-palmer/pynput/issues/628` — pynput Wayland broken, confirmed Feb 2025 (HIGH confidence)
- `https://github.com/moses-palmer/pystray/issues/174` — pystray Wayland status: maintainer closed as "Wayland has no tray API, use AppIndicator" (HIGH confidence)
- `https://pypi.org/project/desktop-notifier/` — desktop-notifier backends and Wayland compatibility (MEDIUM confidence; D-Bus notifications work on Wayland but compositor must run a notification daemon)
- `https://docs.astral.sh/ruff/` — Ruff feature set and version (HIGH confidence)
- WebSearch: pyaudio vs sounddevice, pystray Wayland, pynput Wayland 2025 — (MEDIUM confidence, corroborated by official docs)

---

*Stack research for: Murmur — system-wide voice dictation daemon*
*Researched: 2026-02-17*
