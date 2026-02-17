# Phase 1: Foundation - Context

**Gathered:** 2025-02-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Restructure the existing flat prototype files into a proper `murmur/` Python package with subpackages. Add pyproject.toml (uv + hatchling), Pyright strict mode, pytest suite with mocked backends, and Ruff linting. Add a setup.sh script for system dependencies and venv creation.

</domain>

<decisions>
## Implementation Decisions

### Package structure
- Root package is `murmur/` (not `dictation/` as in early prototype)
- Subpackages: `hotkey/`, `transcriber/`, `injector/`, `feedback/`
- Each subpackage has `base.py` (ABC), concrete backends, and `__init__.py` (factory)
- Entry point: `python -m murmur` via `murmur/__main__.py`
- Follow the structure from VISION.md but with `murmur/` as root

### Build system
- **uv** for project management and venv creation
- **hatchling** as the build backend in pyproject.toml
- `pip install -e .` and `uv pip install -e .` both work (standard PEP 517)
- Optional dependency groups for future extensibility (e.g. `[dev]` for test/lint tools)

### setup.sh script
- Checks and installs system dependencies (ydotool, portaudio, etc.)
- Detects distro (Arch, Debian/Ubuntu, Fedora) for package manager
- Creates venv using uv
- Installs project in editable mode with dev dependencies
- Checks `input` group membership, advises if missing
- Checks ydotoold daemon status

### Type checking
- Pyright strict mode — zero errors, every function annotated
- `Any` treated as a code smell per VISION.md engineering standards
- Pyright config in pyproject.toml

### Linting and formatting
- Ruff for both linting and formatting (replaces Black + isort + Flake8)
- Config in pyproject.toml
- Standard defaults — no unusual rule overrides

### Test strategy
- pytest with mocked backends — no hardware required for unit tests
- Mock boundaries: `subprocess.run` (ydotool), evdev `InputDevice` (synthesized events), AssemblyAI `StreamingClient`
- `pytest.mark.hardware` marker for integration tests requiring real devices
- Tests in `tests/` directory at project root (not inside package)

### Module migration
- Existing flat files (main.py, config.py, etc.) move into `murmur/` package
- Existing ABCs and implementations preserved — this is restructuring, not rewriting
- Imports updated to relative within package

### Claude's Discretion
- Exact Ruff rule configuration
- pytest fixture design and conftest organization
- pyproject.toml metadata details (description, classifiers, URLs)
- Line length preference (88 or 120)

</decisions>

<specifics>
## Specific Ideas

- VISION.md has a detailed target structure — use it as the blueprint but with `murmur/` root
- Engineering standards from VISION.md: "each decision about platform detection, key mapping, and audio format lives in exactly one place"
- "The goal is a codebase where any single file can be read top-to-bottom and understood in isolation"
- Dependencies are minimal and justified: assemblyai, pyaudio, evdev — nothing gratuitous

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2025-02-17*
