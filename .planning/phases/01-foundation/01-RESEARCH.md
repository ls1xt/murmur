# Phase 1: Foundation - Research

**Researched:** 2026-02-17
**Domain:** Python package restructuring, build tooling, static typing, testing infrastructure
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Package structure**
- Root package is `murmur/` (not `dictation/` as in early prototype)
- Subpackages: `hotkey/`, `transcriber/`, `injector/`, `feedback/`
- Each subpackage has `base.py` (ABC), concrete backends, and `__init__.py` (factory)
- Entry point: `python -m murmur` via `murmur/__main__.py`
- Follow the structure from VISION.md but with `murmur/` as root

**Build system**
- **uv** for project management and venv creation
- **hatchling** as the build backend in pyproject.toml
- `pip install -e .` and `uv pip install -e .` both work (standard PEP 517)
- Optional dependency groups for future extensibility (e.g. `[dev]` for test/lint tools)

**setup.sh script**
- Checks and installs system dependencies (ydotool, portaudio, etc.)
- Detects distro (Arch, Debian/Ubuntu, Fedora) for package manager
- Creates venv using uv
- Installs project in editable mode with dev dependencies
- Checks `input` group membership, advises if missing
- Checks ydotoold daemon status

**Type checking**
- Pyright strict mode — zero errors, every function annotated
- `Any` treated as a code smell per VISION.md engineering standards
- Pyright config in pyproject.toml

**Linting and formatting**
- Ruff for both linting and formatting (replaces Black + isort + Flake8)
- Config in pyproject.toml
- Standard defaults — no unusual rule overrides

**Test strategy**
- pytest with mocked backends — no hardware required for unit tests
- Mock boundaries: `subprocess.run` (ydotool), evdev `InputDevice` (synthesized events), AssemblyAI `StreamingClient`
- `pytest.mark.hardware` marker for integration tests requiring real devices
- Tests in `tests/` directory at project root (not inside package)

**Module migration**
- Existing flat files (main.py, config.py, etc.) move into `murmur/` package
- Existing ABCs and implementations preserved — this is restructuring, not rewriting
- Imports updated to relative within package

### Claude's Discretion

- Exact Ruff rule configuration
- pytest fixture design and conftest organization
- pyproject.toml metadata details (description, classifiers, URLs)
- Line length preference (88 or 120)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FOUND-01 | Project restructured into `murmur/` package with `hotkey/`, `transcriber/`, `injector/`, `feedback/` subpackages | Package structure section: existing flat files already use package-relative imports (`from .base import ...`), making migration straightforward |
| FOUND-02 | `pyproject.toml` with dependencies, entry points (`python -m murmur`), and optional dependency groups | Build system section: hatchling + `[dependency-groups]` table (PEP 735), `[project.scripts]` not needed — `__main__.py` handles `python -m murmur` |
| FOUND-03 | All modules pass Pyright strict mode with zero errors | Type checking section: strict mode config in `[tool.pyright]`, key pitfalls documented |
| FOUND-04 | pytest suite with unit tests using mocked backends (evdev, ydotool, AssemblyAI) | Test strategy section: mock boundaries, fixture patterns, conftest layout |
| FOUND-05 | Integration test tier gated behind `pytest.mark.hardware` | Custom markers section: registered in `[tool.pytest.ini_options]`, skip logic in conftest.py |
| FOUND-06 | Ruff formatting and linting enforced across all modules | Ruff section: `[tool.ruff]` + `[tool.ruff.lint]` + `[tool.ruff.format]` configuration |
</phase_requirements>

---

## Summary

This phase restructures the existing flat-file Python prototype into a proper installable package. The prototype code is already written in the target style — the flat files at the project root use package-relative imports (`from .base import HotkeyListener`, `from ..config import TranscriberConfig`), meaning they were designed to live inside subpackages. Migration is primarily scaffolding work: creating `__init__.py` files, `base.py` ABCs, and moving files to their correct locations.

The build tooling stack (uv 0.10.2 + hatchling) is the current idiomatic Python choice as of 2026. uv provides the `[dependency-groups]` table (PEP 735) for dev dependencies, which is distinct from `[project.optional-dependencies]` (extras). The `python -m murmur` entry point requires only a `murmur/__main__.py` — no `[project.scripts]` entry in pyproject.toml is needed.

Pyright strict mode is the highest-friction part of this phase. The existing prototype uses `Optional` from `typing` (legacy style) and contains `type: ignore` comments in evdev_listener.py. Strict mode adds ~30 additional diagnostic rules beyond standard, primarily around unknown types, unannotated parameters, and unused imports. The most common blockers will be: third-party libraries without stubs (`evdev`, `pyaudio`), `Optional[str]` needing explicit handling, and `Type[StreamingClient]` in callback signatures. pytest-mock (via `mocker` fixture) is the standard approach for mocking; pytest-subprocess is optional but useful for ydotool subprocess mocking.

**Primary recommendation:** Scaffold the package structure first, then get Pyright strict passing module-by-module, then write tests against the now-typed interfaces.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| hatchling | latest | Build backend for pyproject.toml | Default backend for `uv init`, pure Python, zero config for standard layouts |
| uv | 0.10.2 (installed) | Project/venv management | Replaces pip+venv+pip-tools; fastest Python package manager; `[dependency-groups]` support |
| pyright | latest | Static type checking (strict) | Locked decision; best strict-mode enforcement; fast, IDE-integrated |
| ruff | latest | Linting + formatting | Replaces Black + isort + Flake8; single tool, single config section |
| pytest | >=8.1 | Test runner | Standard; `[tool.pytest.ini_options]` in pyproject.toml supported since pytest 6.0 |
| pytest-mock | latest | `mocker` fixture for mocking | Thin wrapper over `unittest.mock`; auto-undoes mocks; standard pytest mocking approach |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-subprocess | latest | Fake subprocess results via `fp` fixture | Cleaner than `mocker.patch('subprocess.run')` for ydotool injection testing |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| hatchling | uv_build (uv's own backend) | uv_build is newer and tighter uv integration; hatchling is the locked decision |
| hatchling | setuptools | setuptools is legacy; no reason to use it for a new project |
| pyright | mypy | mypy is slower, less strict by default; pyright is locked decision |
| pytest-mock | `unittest.mock` directly | pytest-mock adds auto-cleanup, `mocker.spy`, better pytest integration |

**Installation (dev dependencies via uv):**
```bash
uv add --dev pyright ruff pytest pytest-mock
# optional for subprocess testing:
uv add --dev pytest-subprocess
```

---

## Architecture Patterns

### Target Package Structure

```
murmur/                          # project root
├── pyproject.toml
├── setup.sh
├── README.md
├── VISION.md
│
├── murmur/                      # installable package
│   ├── __init__.py              # package version, exports
│   ├── __main__.py              # python -m murmur entry point
│   ├── main.py                  # DictationApp orchestrator (from root main.py)
│   ├── config.py                # dataclass config (from root config.py)
│   │
│   ├── hotkey/
│   │   ├── __init__.py          # factory: create_hotkey_listener(config) -> HotkeyListener
│   │   ├── base.py              # HotkeyListener ABC
│   │   └── evdev_listener.py   # EvdevHotkeyListener (from root evdev_listener.py)
│   │
│   ├── transcriber/
│   │   ├── __init__.py          # factory: create_transcriber(config) -> Transcriber
│   │   ├── base.py              # Transcriber ABC
│   │   └── assemblyai.py        # AssemblyAITranscriber (from root assemblyai_transcriber.py)
│   │
│   ├── injector/
│   │   ├── __init__.py          # factory: create_injector(config) -> TextInjector
│   │   ├── base.py              # TextInjector ABC
│   │   └── ydotool.py           # YdotoolInjector (from root ydotool_injector.py)
│   │
│   └── feedback/
│       ├── __init__.py
│       └── audio.py             # AudioFeedback (inline in prototype, extract here)
│
└── tests/
    ├── conftest.py              # shared fixtures, pytest.mark.hardware skip logic
    ├── test_config.py
    ├── test_hotkey.py
    ├── test_transcriber.py
    ├── test_injector.py
    └── test_feedback.py
```

**Note on file renames:** The prototype has `assemblyai_transcriber.py` and `evdev_listener.py` as flat file names. Inside subpackages, cleaner names are `assemblyai.py` and `evdev.py` (the subpackage name already provides context). This is Claude's discretion.

### Pattern 1: ABC Base Class Structure

Each subpackage's `base.py` defines an ABC with abstract methods. Concrete backends subclass it. The `__init__.py` factory function selects the right backend based on config.

```python
# murmur/hotkey/base.py
from abc import ABC, abstractmethod
from collections.abc import Callable

class HotkeyListener(ABC):
    def __init__(self, mode: str = "push_to_talk") -> None:
        self.mode = mode
        self._on_activate: Callable[[], None] | None = None
        self._on_deactivate: Callable[[], None] | None = None

    def set_callbacks(
        self,
        on_activate: Callable[[], None],
        on_deactivate: Callable[[], None],
    ) -> None:
        self._on_activate = on_activate
        self._on_deactivate = on_deactivate

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    def _handle_hotkey_press(self) -> None:
        if self.mode == "push_to_talk" and self._on_activate:
            self._on_activate()
        elif self.mode == "toggle":
            # toggle logic here
            ...

    def _handle_hotkey_release(self) -> None:
        if self.mode == "push_to_talk" and self._on_deactivate:
            self._on_deactivate()
```

**Pyright strict note:** Use `Callable[[], None] | None` (Python 3.10+ union syntax) instead of `Optional[Callable[[], None]]`. Since `requires-python = ">=3.10"`, the `X | Y` union syntax is valid at runtime (not just with `from __future__ import annotations`).

### Pattern 2: Factory Function in `__init__.py`

```python
# murmur/hotkey/__init__.py
from murmur.config import HotkeyConfig
from murmur.hotkey.base import HotkeyListener

def create_hotkey_listener(config: HotkeyConfig) -> HotkeyListener:
    match config.backend:
        case "evdev":
            from murmur.hotkey.evdev import EvdevHotkeyListener
            return EvdevHotkeyListener(
                modifiers=config.modifiers,
                trigger=config.trigger,
                mode=config.mode,
                device_path=config.evdev_device,
            )
        case "auto":
            import sys
            if sys.platform == "linux":
                from murmur.hotkey.evdev import EvdevHotkeyListener
                return EvdevHotkeyListener(...)
            # fallback
            raise RuntimeError(f"No hotkey backend available for {sys.platform}")
        case _:
            raise ValueError(f"Unknown hotkey backend: {config.backend!r}")
```

**Pyright strict note:** `match` with exhaustive `case _` satisfies `reportMatchNotExhaustive`. Lazy imports inside `case` blocks are acceptable and avoid importing platform-specific modules (evdev on Linux, pynput on macOS) at module load time.

### Pattern 3: `__main__.py` Entry Point

```python
# murmur/__main__.py
from murmur.main import main

if __name__ == "__main__":
    main()
```

This is the only content needed in `__main__.py`. `python -m murmur` executes this file.

### Pattern 4: pyproject.toml Structure

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "murmur"
version = "0.1.0"
description = "System-wide voice dictation for Linux/Wayland"
requires-python = ">=3.10"
dependencies = [
    "assemblyai>=0.33.0",
    "pyaudio>=0.2.14",
    "evdev>=1.7.0",
]

[dependency-groups]
dev = [
    "pyright>=1.1.0",
    "ruff>=0.9.0",
    "pytest>=8.1.0",
    "pytest-mock>=3.14.0",
]

[tool.pyright]
typeCheckingMode = "strict"
pythonVersion = "3.10"

[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM"]
# E = pycodestyle errors, F = pyflakes, I = isort, N = pep8 naming,
# UP = pyupgrade, B = flake8-bugbear, SIM = flake8-simplify

[tool.ruff.format]
quote-style = "double"
docstring-code-format = true

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "hardware: marks tests that require real hardware (evdev device, ydotool daemon)",
]
```

**Key distinction:** `[dependency-groups]` (PEP 735, uv-specific) is for dev/test tools that are NOT published with the package. `[project.optional-dependencies]` is for user-facing extras (e.g., a future `murmur[whisper]` extra). Use `[dependency-groups]` for pyright/ruff/pytest.

### Pattern 5: pytest Custom Marker with Skip Logic

```python
# tests/conftest.py
import pytest

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "hardware: marks tests requiring real hardware (skip with -m 'not hardware')"
    )

def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    # Auto-skip hardware tests unless --hardware flag is passed
    if not config.getoption("--hardware", default=False):
        skip_hw = pytest.mark.skip(reason="requires --hardware flag")
        for item in items:
            if item.get_closest_marker("hardware"):
                item.add_marker(skip_hw)

def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--hardware",
        action="store_true",
        default=False,
        help="Run hardware-gated integration tests",
    )
```

Alternatively, the simpler approach: register the marker and let users use `pytest -m 'not hardware'` to skip. Auto-skip is ergonomically better for a CI-first workflow.

### Pattern 6: Mock Boundaries for Unit Tests

**YdotoolInjector — mock `subprocess.run`:**
```python
# tests/test_injector.py
from unittest.mock import MagicMock, patch
from murmur.injector.ydotool import YdotoolInjector
from murmur.config import InjectorConfig

def test_inject_calls_ydotool(mocker: pytest.MockerFixture) -> None:
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0)
    mocker.patch("shutil.which", return_value="/usr/bin/ydotool")

    injector = YdotoolInjector(ydotool_path="ydotool", key_delay=0, trailing_space=False)
    injector.inject("hello world")

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "ydotool" in args[0]
    assert "hello world" in args
```

**EvdevHotkeyListener — synthesized events:**
```python
# tests/test_hotkey.py
from unittest.mock import MagicMock, patch, call
import evdev
from murmur.hotkey.evdev import EvdevHotkeyListener

def test_hotkey_fires_on_combo(mocker: pytest.MockerFixture) -> None:
    mock_device = MagicMock(spec=evdev.InputDevice)
    mocker.patch("evdev.list_devices", return_value=["/dev/input/event0"])
    mocker.patch("evdev.InputDevice", return_value=mock_device)

    on_activate = MagicMock()
    listener = EvdevHotkeyListener(
        modifiers=["KEY_LEFTCTRL", "KEY_LEFTSHIFT"],
        trigger="KEY_SPACE",
        mode="push_to_talk",
    )
    listener.set_callbacks(on_activate=on_activate, on_deactivate=MagicMock())

    # Synthesize key events directly by calling _handle_key_event
    ctrl_down = MagicMock()
    ctrl_down.type = evdev.ecodes.EV_KEY
    ctrl_down.code = evdev.ecodes.KEY_LEFTCTRL
    # ... (see code examples below for full synthesis pattern)
```

**AssemblyAI Transcriber — mock the StreamingClient:**
```python
# tests/test_transcriber.py
from unittest.mock import MagicMock, patch
from murmur.transcriber.assemblyai import AssemblyAITranscriber
from murmur.config import TranscriberConfig

def test_transcriber_starts_client(mocker: pytest.MockerFixture) -> None:
    mock_client = MagicMock()
    mocker.patch("assemblyai.streaming.v3.StreamingClient", return_value=mock_client)
    mocker.patch("assemblyai.extras.MicrophoneStream")

    config = TranscriberConfig(api_key="test_key", sample_rate=16000, format_turns=True)
    transcriber = AssemblyAITranscriber(config)
    transcriber.start()

    mock_client.connect.assert_called_once()
```

### Anti-Patterns to Avoid

- **Importing evdev at module level in `base.py`**: evdev is Linux-only; importing it in the ABC breaks macOS. Lazy-import inside the factory or the concrete class.
- **Putting dev dependencies in `[project.optional-dependencies]`**: Those get published to PyPI. Dev tools go in `[dependency-groups]`.
- **Using `Optional[X]` from `typing` in new code**: With `requires-python = ">=3.10"`, use `X | None` syntax. Pyright strict will accept both, but `UP` (pyupgrade) ruff rule will flag the old form.
- **`pyrightconfig.json` alongside `pyproject.toml`**: Pyright gives `pyrightconfig.json` precedence over `pyproject.toml [tool.pyright]`. Use only `pyproject.toml` to keep config consolidated.
- **Running `pytest` without the `tests/` testpath config**: Without `testpaths = ["tests"]`, pytest discovers tests in the package itself too, which can cause import confusion with the installed editable package.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Mock cleanup after tests | Manual `patch.stop()` calls | `pytest-mock` `mocker` fixture | Auto-undoes patches at test end; cleaner than `with patch(...)` blocks |
| Subprocess mocking | Parse `subprocess.run` args manually | `pytest-subprocess` `fp` fixture or `mocker.patch` | Edge cases with timeout, capture_output, shell=True |
| Custom test skip logic | Manual `if` checks in each test | `pytest.mark.hardware` + conftest skip | Composable, readable, CLI-filterable |
| Type stub generation | Write `.pyi` files manually | `pyright --createstub evdev` or ignore with `# type: ignore` | Only worth it for heavily-used libraries; `evdev` types are thin |

**Key insight:** The `mocker` fixture from `pytest-mock` is strictly better than raw `unittest.mock.patch` in pytest tests — it auto-cleans up and integrates with pytest's fixture system.

---

## Common Pitfalls

### Pitfall 1: Third-Party Library Missing Type Stubs

**What goes wrong:** Pyright strict mode reports `reportMissingModuleSource` or `reportUnknownMemberType` for `evdev`, `pyaudio`, and potentially `assemblyai`. These libraries either lack stubs or have incomplete type information.

**Why it happens:** Pyright strict's `reportUnknownVariableType` and related rules flag any value whose type cannot be statically determined.

**How to avoid:**
1. Check if `types-*` stub packages exist on PyPI (e.g., `types-pyaudio` — check if it exists, but likely doesn't)
2. For `evdev`: add `"evdev"` to `[tool.pyright] ignore` list, or use `# type: ignore[import-untyped]` at import sites
3. For `assemblyai`: the assemblyai SDK ships with inline types as of recent versions — verify by running `pyright` and checking errors
4. For `pyaudio`: likely needs `# type: ignore[import-untyped]` or a minimal local stub

**Warning signs:** Errors like `Import "evdev" could not be resolved from source` or `Type of "XYZ" is partially unknown`.

**Recommended approach:**
```toml
# pyproject.toml
[tool.pyright]
typeCheckingMode = "strict"
pythonVersion = "3.10"
# For libraries without stubs, suppress the specific diagnostic:
reportMissingModuleSource = "none"
```

Or at import site:
```python
import pyaudio  # type: ignore[import-untyped]
```

### Pitfall 2: `Type[StreamingClient]` in Callback Signatures

**What goes wrong:** The existing `assemblyai_transcriber.py` uses `Type[StreamingClient]` as the first argument type for event handlers. In strict mode, this is likely inaccurate — the SDK probably passes the instance, not the class.

**Why it happens:** The prototype was written before strict type checking was enforced.

**How to avoid:** Verify the actual type the AssemblyAI SDK passes to event handlers, then annotate correctly. May need to use `Any` with a comment, or check if the SDK exposes a protocol type. Look at the SDK's type annotations for `StreamingClient.on()`.

**Warning signs:** `reportArgumentType` errors when registering callbacks.

### Pitfall 3: `_from_dict` in config.py Uses `setattr` with Untyped Values

**What goes wrong:** `config.py`'s `_from_dict` uses `setattr(config.hotkey, k, v)` where `v` is `Any` from JSON. Pyright strict flags this as assigning an unknown type to a typed field.

**Why it happens:** The current pattern deliberately avoids type-safe deserialization. Strict mode catches it.

**How to avoid:** Either use a type-safe approach (e.g., `dataclasses.replace`, explicit field mapping) or annotate `_from_dict` to suppress the specific warning with a targeted `# type: ignore`. Since this is a Phase 1 restructuring (not a rewrite), suppressing with a comment and a TODO is acceptable.

**Warning signs:** `reportUnknownVariableType` or `reportArgumentType` in `config.py`.

### Pitfall 4: `evdev_listener.py` Has `# type: ignore` Comments

**What goes wrong:** The existing `evdev_listener.py` line 136 has `# type: ignore` for `key.fileobj`. This is legitimate (evdev's type stubs don't fully type `SelectorKey.fileobj`). Keep these suppression comments — they are intentional, not sloppy.

**How to avoid:** Accept existing `# type: ignore` comments for third-party library limitations. Document them with specific codes: `# type: ignore[assignment]` rather than bare `# type: ignore`.

### Pitfall 5: `[dependency-groups]` vs `[project.optional-dependencies]`

**What goes wrong:** Confusing the two causes dev tools to be published to PyPI as user-facing extras, or causes `pip install murmur[dev]` to work but `uv sync --dev` to fail.

**Why it happens:** `[dependency-groups]` (PEP 735) is a uv-specific extension not yet universal. `[project.optional-dependencies]` is the PEP 517/518 standard for extras.

**How to avoid:**
- `[dependency-groups]` for dev/test/lint tools (never published, local only)
- `[project.optional-dependencies]` for user-facing optional features (e.g., `murmur[whisper]` in future)
- Install dev group: `uv sync --dev` or `uv pip install -e ".[dev]"` won't work for dependency-groups; use `uv sync`

**Warning signs:** `pip install -e ".[dev]"` fails to find dev group. Note: `pip` does NOT understand `[dependency-groups]` — only `uv sync` does. If `pip install -e .` compatibility is required for dev tools, put them in `[project.optional-dependencies]` instead.

**Resolution:** Since the locked decision says "both `pip install -e .` and `uv pip install -e .` work", the core package install works. Dev tools only need to work via uv. Use `[dependency-groups]` for dev tools, install via `uv sync`.

### Pitfall 6: `setup.sh` Creating venv Then Installing

**What goes wrong:** `uv venv` creates a venv; then `uv pip install -e .` needs to target that venv. If the script doesn't activate the venv or use `--python .venv/bin/python`, the install may go to the system Python.

**How to avoid:**
```bash
uv venv .venv
uv pip install -e ".[dev]" --python .venv/bin/python
# or simply:
uv sync  # reads pyproject.toml, creates .venv automatically, installs everything
```
`uv sync` is the idiomatic uv command — it creates the venv if absent, installs all groups by default. Prefer `uv sync` over `uv venv && uv pip install`.

---

## Code Examples

Verified patterns from official sources and current codebase analysis:

### Complete pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "murmur"
version = "0.1.0"
description = "System-wide voice dictation for Linux/Wayland"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
dependencies = [
    "assemblyai>=0.33.0",
    "pyaudio>=0.2.14",
    "evdev>=1.7.0; sys_platform == 'linux'",
]

[dependency-groups]
dev = [
    "pyright>=1.1.0",
    "ruff>=0.9.0",
    "pytest>=8.1.0",
    "pytest-mock>=3.14.0",
]

[tool.pyright]
typeCheckingMode = "strict"
pythonVersion = "3.10"
reportMissingModuleSource = "none"

[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM"]
ignore = ["N815"]  # allow mixedCase for evdev key constants if needed

[tool.ruff.format]
quote-style = "double"
docstring-code-format = true

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "hardware: marks tests that require real hardware (evdev device, ydotoold daemon)",
]
```

**Note on `evdev` platform marker:** `evdev>=1.7.0; sys_platform == 'linux'` ensures `pip install` on macOS doesn't fail trying to install evdev (which is Linux-only). This is important for portability.

### setup.sh Pattern

```bash
#!/usr/bin/env bash
set -euo pipefail

# Detect distro via /etc/os-release
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO="${ID:-unknown}"
else
    DISTRO="unknown"
fi

# Install system dependencies
case "$DISTRO" in
    arch|manjaro)
        sudo pacman -S --needed ydotool portaudio
        ;;
    ubuntu|debian|linuxmint)
        sudo apt-get install -y ydotool portaudio19-dev
        ;;
    fedora)
        sudo dnf install -y ydotool portaudio-devel
        ;;
    *)
        echo "WARNING: Unknown distro '$DISTRO'. Install ydotool and portaudio manually."
        ;;
esac

# Check input group membership
if ! groups | grep -qw input; then
    echo "WARNING: You are not in the 'input' group."
    echo "  Run: sudo usermod -aG input \$USER"
    echo "  Then log out and back in."
fi

# Check ydotoold status
if ! pgrep -x ydotoold > /dev/null 2>&1; then
    echo "WARNING: ydotoold daemon is not running."
    echo "  Start it: systemctl --user start ydotool"
fi

# Create venv and install
uv sync

echo "Done. Activate with: source .venv/bin/activate"
echo "Run with: python -m murmur"
```

### Pyright Strict — Handling Unknown Types from Third-Party Libraries

```python
# murmur/transcriber/assemblyai.py

# For libraries that lack complete type stubs:
import pyaudio  # type: ignore[import-untyped]
import assemblyai as aai

# Use explicit type annotations everywhere:
def _stream_audio(self) -> None:
    """Stream microphone audio (runs in background thread)."""
    mic: aai.extras.MicrophoneStream | None = None
    try:
        mic = aai.extras.MicrophoneStream(sample_rate=self._config.sample_rate)
        if self._client is not None:
            self._client.stream(mic)
    except Exception as exc:
        if self._is_streaming and self._on_error is not None:
            self._on_error(exc)
```

### pytest conftest.py — Hardware Skip Logic

```python
# tests/conftest.py
from __future__ import annotations
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--hardware",
        action="store_true",
        default=False,
        help="Run integration tests requiring real hardware",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    if config.getoption("--hardware"):
        return  # don't skip anything
    skip_marker = pytest.mark.skip(reason="hardware tests skipped (use --hardware to run)")
    for item in items:
        if item.get_closest_marker("hardware"):
            item.add_marker(skip_marker)
```

### Synthesizing evdev Events for Unit Tests

```python
# tests/test_hotkey.py
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
import evdev
from murmur.hotkey.evdev import EvdevHotkeyListener


def make_key_event(code: int, value: int) -> evdev.InputEvent:
    """Create a synthetic EV_KEY event (value: 0=up, 1=down, 2=hold)."""
    event = MagicMock(spec=evdev.InputEvent)
    event.type = evdev.ecodes.EV_KEY
    event.code = code
    event.value = value
    return event


def test_push_to_talk_fires_callbacks() -> None:
    on_activate = MagicMock()
    on_deactivate = MagicMock()

    listener = EvdevHotkeyListener(
        modifiers=["KEY_LEFTCTRL", "KEY_LEFTSHIFT"],
        trigger="KEY_SPACE",
        mode="push_to_talk",
    )
    listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

    # Simulate: Ctrl down, Shift down, Space down -> activate
    listener._held_keys.add(evdev.ecodes.KEY_LEFTCTRL)
    listener._held_keys.add(evdev.ecodes.KEY_LEFTSHIFT)

    space_down = make_key_event(evdev.ecodes.KEY_SPACE, 1)
    listener._handle_key_event(space_down)
    on_activate.assert_called_once()

    # Simulate: Space up -> deactivate
    space_up = make_key_event(evdev.ecodes.KEY_SPACE, 0)
    listener._handle_key_event(space_up)
    on_deactivate.assert_called_once()
```

**Note on `_handle_key_event` visibility:** The method is named with a single underscore (protected, not private). Tests CAN call it directly — this is the right approach for testing event-driven internal logic without running the full listener loop.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `from typing import Optional, List, Tuple` | `X \| None`, `list[X]`, `tuple[X, ...]` | Python 3.10+ | Pyright UP rule (pyupgrade) will flag old-style in new code |
| `setup.py` + `requirements.txt` | `pyproject.toml` with hatchling | PEP 517/518 (2017), now universal | `pip install -e .` works directly from pyproject.toml |
| `pip` + `virtualenv` | `uv sync` | uv 0.1 (2024) | 10-100x faster; unified venv + install |
| `pytest.ini` or `setup.cfg` | `[tool.pytest.ini_options]` in pyproject.toml | pytest 6.0 (2020) | Single config file |
| `black` + `isort` + `flake8` | `ruff check` + `ruff format` | ruff 0.1 (2023) | Single binary, same behavior |
| `[project.optional-dependencies]` for dev tools | `[dependency-groups]` (PEP 735) | uv 0.4+ | Not published to PyPI; `uv sync` handles it |

**Deprecated/outdated:**
- `from __future__ import annotations`: Was needed for forward references in Python 3.7-3.9. With `requires-python = ">=3.10"`, it's only needed for cross-module forward references in some edge cases. Ruff's `UP` rules will flag unnecessary uses.
- `typing.Optional`, `typing.List`, `typing.Dict`: Replaced by `X | None`, `list[X]`, `dict[K, V]` in Python 3.10+.

---

## Open Questions

1. **Does the `assemblyai` SDK ship complete type stubs?**
   - What we know: The SDK uses `StreamingClient` with a callback system that takes `(client, event)` — the existing code annotates the first arg as `Type[StreamingClient]` which is likely wrong (it's the instance, not the class)
   - What's unclear: Whether `assemblyai>=0.33.0` exports typed interfaces or requires `# type: ignore`
   - Recommendation: Run `pyright` on the existing transcriber file immediately after restructuring to get the actual error count and error types before over-engineering a solution

2. **Does `pyaudio` have a `types-pyaudio` stub package?**
   - What we know: `pyaudio` is old and likely lacks stubs; the project uses it only for `MicrophoneStream` via the assemblyai SDK
   - What's unclear: Whether `aai.extras.MicrophoneStream` is the only `pyaudio` surface that needs typing
   - Recommendation: Check `pip index versions types-pyaudio` — if no stubs exist, use `reportMissingModuleSource = "none"` in pyright config

3. **Line length: 88 or 120?**
   - 88 is Black/Ruff default (locked in by the project VISION's "Ruff formatting" reference)
   - 120 is used by some projects for wider monitors
   - Recommendation: 88 (default) unless there's a specific reason; the existing code has some long lines that would need wrapping at 88

4. **Should `evdev` be a conditional dependency?**
   - The locked decision targets Linux (Wayland), and evdev is Linux-only
   - `evdev>=1.7.0; sys_platform == 'linux'` prevents install failures on macOS
   - This should be included in the final pyproject.toml

---

## Sources

### Primary (HIGH confidence)

- uv official docs (https://docs.astral.sh/uv/concepts/projects/dependencies/) — `[dependency-groups]` syntax, `uv add --dev`, `uv sync`
- Pyright configuration docs (https://raw.githubusercontent.com/microsoft/pyright/main/docs/configuration.md) — `[tool.pyright]` in pyproject.toml, strict mode rules
- Ruff configuration docs (https://docs.astral.sh/ruff/configuration/) — `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.format]` structure
- pytest docs (https://docs.pytest.org/en/stable/how-to/mark.html) — custom marker registration, `[tool.pytest.ini_options]`
- Python packaging guide (https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) — hatchling build-backend syntax

### Secondary (MEDIUM confidence)

- WebSearch: pyproject.toml hatchling + uv examples — confirmed by official uv docker example on GitHub
- WebSearch: Pyright strict mode diagnostics — cross-referenced with official configuration.md

### Tertiary (LOW confidence)

- assemblyai SDK type stub completeness — not verified; needs empirical check after restructuring
- pyaudio type stubs availability — not verified; likely absent based on library age

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — uv 0.10.2 is installed, hatchling is default for uv, all tool versions verified via official docs
- Architecture: HIGH — package structure follows established Python packaging conventions; existing code already uses relative imports expecting this structure
- Pitfalls: MEDIUM-HIGH — most pitfalls from direct code analysis + official Pyright docs; assemblyai stub question is LOW

**Research date:** 2026-02-17
**Valid until:** 2026-04-17 (60 days — stable tooling, no fast-moving components)
