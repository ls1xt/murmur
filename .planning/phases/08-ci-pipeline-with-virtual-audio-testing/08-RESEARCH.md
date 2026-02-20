# Phase 8: CI Pipeline with Virtual Audio Testing - Research

**Researched:** 2026-02-20
**Domain:** GitHub Actions CI, pytest virtual audio, pre-commit hooks
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **CI platform:** GitHub Actions, single workflow file `ci.yml`, triggers on push and pull_request
- **Matrix:** `ubuntu-latest` + `macos-latest`, Python `3.11` + `3.12`
- **Dependency install:** `astral-sh/setup-uv` (project already uses uv)
- **Fail fast:** Default (cancel remaining matrix jobs on first failure)
- **What CI enforces:**
  - `ruff check .` — linting
  - `ruff format --check .` — formatting
  - `pyright` — type checking
  - `pytest` — unit tests (fully mocked, no hardware)
  - `pytest --virtual-mic` — audio pipeline tests using virtual mic device
  - `pre-commit run --all-files` — all pre-commit hooks
- **Virtual mic (Linux):** `snd-aloop` ALSA loopback kernel module (`sudo modprobe snd-aloop`); creates virtual soundcard that sounddevice/PortAudio sees as ALSA input
- **Virtual mic (macOS):** BlackHole 2ch (`brew install blackhole-2ch`); same `--virtual-mic` flag and fixture mechanism
- **Test tiers:**
  - `pytest` — unit only (fully mocked, always runs)
  - `pytest --virtual-mic` — unit + audio pipeline (CI + local with driver loaded)
  - `pytest --hardware` — everything including real-mic e2e (local only, existing flag)
  - New `--virtual-mic` flag added to `conftest.py` alongside existing `--hardware`
- **Test marker:** `@pytest.mark.requires_virtual_mic`; skipped unless `--virtual-mic` passed
- **`conftest.py` fixture:** `virtual_mic_device` — session-scoped, yields loopback device index/name
- **Pre-commit hooks:**
  - `ruff` lint + format via `astral-sh/ruff-pre-commit`
  - `pyright` type checking via local env / pre-commit mirror
  - `check-added-large-files` — reject files > 500 KB
  - `detect-secrets` — scan for API keys, tokens, private keys
  - `check-jupyter` / `check-case-conflict` / forbid `.ipynb` files
  - `trailing-whitespace` + `end-of-file-fixer`
- **CI step order:** setup virtual audio → install deps → pre-commit → lint/type-check → unit tests → virtual-mic tests
- **README badge:** Add GitHub Actions CI status badge once workflow in place

### Claude's Discretion

- Exact `snd-aloop` device index discovery in the fixture
- BlackHole device name detection (e.g. partial match on "BlackHole")
- Whether pyright runs as a pre-commit hook or only directly in CI (pyright in pre-commit can be slow)
- `detect-secrets` baseline file handling

### Deferred Ideas (OUT OF SCOPE)

- Release pipeline (PyPI publish, auto-fill Homebrew SHA256, GitHub Release creation)
- AssemblyAI API key in CI for mid-tier WebSocket tests
- Mock WebSocket server for testing AssemblyAI protocol without API credits
</user_constraints>

---

## Summary

Phase 8 sets up CI infrastructure for the murmur project: a GitHub Actions workflow with a 2×2 matrix (Linux+macOS, Python 3.11+3.12), virtual audio device support for audio pipeline tests, and pre-commit hooks for code quality enforcement. All the key decisions are locked in CONTEXT.md — this is primarily an implementation task, not a design task.

The main implementation complexity lies in: (1) reliably detecting the virtual audio device in fixtures across both platforms, (2) correctly handling the `snd-aloop` module load on Linux (requires `sudo` in CI, always available on `ubuntu-latest` runners), and (3) deciding whether pyright runs in pre-commit or only in CI directly.

**Primary recommendation:** Keep pyright out of pre-commit (run it only in CI directly). Pre-commit pyright is notoriously slow on first run (type stub installation, venv creation) and fails in subtle ways when the pre-commit isolated env differs from the project env. Run `pyright` as a direct CI step using the project's own uv-managed env instead.

---

## Standard Stack

### Core

| Library/Tool | Version | Purpose | Notes |
|---|---|---|---|
| `actions/checkout` | v4 | Checkout repo | Standard; v4 uses Node 20 |
| `astral-sh/setup-uv` | v5 | Install uv + sync deps | Project already uses uv |
| `actions/setup-python` | v5 | Set Python version | Used alongside setup-uv for matrix |
| `ruff` | >=0.9.0 (from pyproject) | Lint + format | Already in dev deps |
| `pyright` | >=1.1.0 (from pyproject) | Type checking | Already in dev deps |
| `pytest` | >=8.1.0 (from pyproject) | Test runner | Already in dev deps |
| `pre-commit` | >=3.0 | Hook runner | To add to dev deps |
| `snd-aloop` | kernel built-in | Linux virtual audio | Available on ubuntu-latest |
| BlackHole 2ch | brew formula | macOS virtual audio | `brew install blackhole-2ch` |

### Pre-commit Hook Sources

| Hook | Repo | Purpose |
|---|---|---|
| `ruff-pre-commit` | `https://github.com/astral-sh/ruff-pre-commit` | Lint + format |
| `pre-commit-hooks` | `https://github.com/pre-commit/pre-commit-hooks` | `trailing-whitespace`, `end-of-file-fixer`, `check-added-large-files`, `check-case-conflict`, `check-jupyter` |
| `detect-secrets` | `https://github.com/Yelp/detect-secrets` | Secret scanning |

### pyright in pre-commit — Decision

**Recommendation: Skip pyright in pre-commit. Run it only as a CI step.**

Rationale:
- Pre-commit creates an isolated virtual env for pyright; it does NOT inherit project stubs or local type annotations
- First run downloads pyright binary + installs type stubs (~30-60s extra, fails if network issues)
- The project uses `pyright` strict mode configured in `pyproject.toml` (`venvPath = "."`, `venv = ".venv"`) — pre-commit's isolated env ignores this
- Running `pyright` directly via `uv run pyright` in CI uses the correct project env

**detect-secrets baseline:** Create `.secrets.baseline` via `detect-secrets scan > .secrets.baseline` and commit it. CI runs `detect-secrets audit --baseline .secrets.baseline`. New secrets fail pre-commit.

---

## Architecture Patterns

### GitHub Actions Workflow Structure

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci:
    name: Python ${{ matrix.python-version }} / ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: true
      matrix:
        os: [ubuntu-latest, macos-latest]
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      # Linux: load ALSA loopback module
      - name: Setup virtual audio (Linux)
        if: runner.os == 'Linux'
        run: sudo modprobe snd-aloop

      # macOS: install BlackHole
      - name: Setup virtual audio (macOS)
        if: runner.os == 'macOS'
        run: brew install blackhole-2ch

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install dependencies
        run: uv sync --group dev

      - name: Run pre-commit
        run: uv run pre-commit run --all-files

      - name: Lint (ruff)
        run: uv run ruff check .

      - name: Format check (ruff)
        run: uv run ruff format --check .

      - name: Type check (pyright)
        run: uv run pyright

      - name: Unit tests
        run: uv run pytest

      - name: Audio pipeline tests (virtual mic)
        run: uv run pytest --virtual-mic
```

### conftest.py Extension Pattern

The existing `conftest.py` has `--hardware` flag + `pytest_addoption` + `pytest_collection_modifyitems`. Extend with the same pattern for `--virtual-mic`:

```python
# In pytest_addoption:
parser.addoption(
    "--virtual-mic",
    action="store_true",
    default=False,
    help="Run audio pipeline tests using virtual mic device (snd-aloop/BlackHole)",
)

# In pytest_collection_modifyitems:
if not config.getoption("--virtual-mic"):
    skip_virtual = pytest.mark.skip(
        reason="virtual-mic tests skipped (use --virtual-mic to run)"
    )
    for item in items:
        if item.get_closest_marker("requires_virtual_mic"):
            item.add_marker(skip_virtual)

# In pyproject.toml markers section:
# "requires_virtual_mic: marks tests that require virtual mic device"

# Session-scoped fixture:
@pytest.fixture(scope="session")
def virtual_mic_device() -> Generator[str | int, None, None]:
    """Yield the virtual mic device name/index for audio pipeline tests."""
    import sounddevice as sd
    import sys

    devices = sd.query_devices()
    if sys.platform == "linux":
        # snd-aloop creates devices named "Loopback: PCM" or similar
        for i, dev in enumerate(devices):
            if "loopback" in dev["name"].lower() and dev["max_input_channels"] > 0:
                yield i
                return
    elif sys.platform == "darwin":
        for i, dev in enumerate(devices):
            if "blackhole" in dev["name"].lower() and dev["max_input_channels"] > 0:
                yield dev["name"]
                return
    pytest.skip("No virtual mic device found — load snd-aloop or install BlackHole")
```

### .pre-commit-config.yaml Pattern

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-added-large-files
        args: [--maxkb=500]
      - id: check-case-conflict
      - id: check-jupyter

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: [--baseline, .secrets.baseline]
```

Note: `.ipynb` file prohibition is achieved via `check-jupyter` from pre-commit-hooks — this hook checks that notebooks are valid JSON; to actually forbid `.ipynb` commits, add a `forbid-new-submodules` or custom hook, or use `check-added-large-files` with file-pattern exclusions. Alternatively, add a `.gitattributes` rule or simply rely on `check-jupyter` to catch broken notebooks. **Simplest approach:** add a `files: \.ipynb$` + `types: [file]` entry under `check-added-large-files` or use a `local` repo hook.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Device index discovery | Custom ALSA/CoreAudio enumeration | `sounddevice.query_devices()` | Cross-platform, handles both backends |
| Virtual device waiting | Sleep loops | Pre-load module before pytest step | `snd-aloop` is synchronous; device available immediately after `modprobe` |
| Pre-commit in CI | Custom hook runner scripts | `pre-commit run --all-files` in CI step | Identical to local; catches drift |
| Secret baseline | Custom secret regex | `detect-secrets` with `.secrets.baseline` | Handles entropy analysis, multiple patterns |

---

## Common Pitfalls

### Pitfall 1: snd-aloop device naming is not deterministic
**What goes wrong:** The loopback device index varies depending on which other audio devices are present on the runner. Hardcoding index `0` or `1` fails.
**Why it happens:** Linux assigns ALSA device numbers dynamically at modprobe time.
**How to avoid:** Always enumerate via `sounddevice.query_devices()` and match by name substring (`"loopback"`).
**Warning signs:** Tests pass locally but fail on CI with "invalid device" errors.

### Pitfall 2: BlackHole device detection on macOS CI
**What goes wrong:** `brew install blackhole-2ch` may take 30-60s; if the step is fast, the device may not appear in `sd.query_devices()` immediately. (Usually it does — PortAudio enumerates on each call.)
**How to avoid:** The fixture should call `sd.query_devices()` fresh each time. No sleep needed — PortAudio re-enumerates. If device still not found, `pytest.skip()` gracefully.

### Pitfall 3: pyright fails in pre-commit due to missing stubs
**What goes wrong:** Pre-commit creates an isolated env that does NOT have the project's dependencies; pyright cannot find `assemblyai`, `evdev`, etc.
**How to avoid:** Skip pyright in pre-commit. Run `uv run pyright` directly in CI as a separate step using the project venv.

### Pitfall 4: pre-commit hooks modify files → test fails
**What goes wrong:** `ruff --fix` in pre-commit modifies files; if CI runs pre-commit + tests in sequence, modified but uncommitted files cause a dirty working tree.
**How to avoid:** Run pre-commit BEFORE tests in CI step order. If files are modified, `pre-commit` exits non-zero (it always does on first run when fixes are applied), which fails CI correctly. Developers fix locally before pushing.

### Pitfall 5: macOS `brew install` on GitHub Actions is slow
**What goes wrong:** `brew install blackhole-2ch` can take 2-5 minutes if brew updates itself first.
**How to avoid:** Add `HOMEBREW_NO_AUTO_UPDATE=1` env var to the macOS setup step:
```yaml
- name: Setup virtual audio (macOS)
  if: runner.os == 'macOS'
  env:
    HOMEBREW_NO_AUTO_UPDATE: "1"
  run: brew install blackhole-2ch
```

### Pitfall 6: detect-secrets baseline not committed
**What goes wrong:** `detect-secrets` fails on the first CI run because `.secrets.baseline` doesn't exist.
**How to avoid:** Generate baseline locally and commit it: `detect-secrets scan > .secrets.baseline && git add .secrets.baseline`.

### Pitfall 7: `uv sync` vs `uv pip install`
**What goes wrong:** Using `uv pip install` or `pip install -e .` instead of `uv sync --group dev` misses the lockfile and may install different versions in CI.
**How to avoid:** Always use `uv sync --group dev` to respect `uv.lock`.

---

## Code Examples

### Verified: sounddevice device enumeration

```python
import sounddevice as sd
import sys

def find_virtual_mic() -> int | str | None:
    """Find the virtual mic device index/name, or return None."""
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        name = dev["name"].lower()
        max_in = dev["max_input_channels"]
        if max_in == 0:
            continue
        if sys.platform == "linux" and "loopback" in name:
            return i
        if sys.platform == "darwin" and "blackhole" in name:
            return dev["name"]
    return None
```

### Verified: pytest marker + addoption pattern (mirrors existing --hardware)

```python
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--hardware", action="store_true", default=False, ...)
    parser.addoption("--virtual-mic", action="store_true", default=False, ...)

def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for flag, marker_name, reason in [
        ("--hardware", "hardware", "use --hardware to run"),
        ("--virtual-mic", "requires_virtual_mic", "use --virtual-mic to run"),
    ]:
        if not config.getoption(flag):
            skip = pytest.mark.skip(reason=f"skipped ({reason})")
            for item in items:
                if item.get_closest_marker(marker_name):
                    item.add_marker(skip)
```

### Verified: GitHub Actions matrix with platform conditionals

```yaml
strategy:
  fail-fast: true
  matrix:
    os: [ubuntu-latest, macos-latest]
    python-version: ["3.11", "3.12"]

steps:
  - name: Setup virtual audio (Linux)
    if: runner.os == 'Linux'
    run: sudo modprobe snd-aloop

  - name: Setup virtual audio (macOS)
    if: runner.os == 'macOS'
    env:
      HOMEBREW_NO_AUTO_UPDATE: "1"
    run: brew install blackhole-2ch
```

### README badge pattern

```markdown
[![CI](https://github.com/berleon/murmur/actions/workflows/ci.yml/badge.svg)](https://github.com/berleon/murmur/actions/workflows/ci.yml)
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|---|---|---|
| `pip install -r requirements.txt` | `uv sync --group dev` | Lockfile-reproducible installs |
| `actions/cache` for pip | `astral-sh/setup-uv` (has built-in caching) | Simpler, faster |
| Separate lint/format tools | `ruff` for both | One tool, 10-100x faster than flake8+isort+black |
| pyright in pre-commit | pyright in CI only | Avoids isolated-env stub issues |
| `setup.py test` | `pytest` direct | Modern standard |

---

## Open Questions

1. **`snd-aloop` loopback device channel count**
   - What we know: `snd-aloop` creates a full duplex loopback with 8 channels by default
   - What's unclear: Does murmur's audio capture code specify a channel count? If it always defaults to 1 channel mono, no issue. If it queries device max channels, snd-aloop's 8-channel default works fine.
   - Recommendation: Check `murmur/transcriber/assemblyai.py` for channel configuration; if it uses `sounddevice.InputStream(channels=1, ...)` then any device with `max_input_channels >= 1` is fine.

2. **`check-jupyter` vs `forbid *.ipynb` — clarify intent**
   - What we know: CONTEXT.md says "forbid `.ipynb` files". `check-jupyter` validates notebooks but does NOT prevent committing new ones.
   - Recommendation: Add a `local` repo hook or a `.gitattributes` deny rule, OR use a simple `check-added-large-files` with `types: [jupyter]` to block new notebooks. Simplest: add a `local` pre-commit hook that fails if any `.ipynb` is staged.

3. **`pre-commit` in dev deps**
   - `pre-commit` is not currently in `pyproject.toml` dev deps
   - Need to add it: `uv add --group dev pre-commit`

---

## Sources

### Primary (HIGH confidence)
- GitHub Actions official docs (actions/checkout@v4, setup-python@v5) — confirmed current versions
- `astral-sh/setup-uv` GitHub README — v5 is current, includes built-in caching
- `sounddevice` docs — `query_devices()` API confirmed
- `snd-aloop` Linux kernel docs — synchronous load, device available immediately
- `pre-commit` official docs — `.pre-commit-config.yaml` format, hook repos
- `astral-sh/ruff-pre-commit` — `ruff` + `ruff-format` hook IDs
- `pre-commit/pre-commit-hooks` v5.0.0 — hook IDs confirmed

### Secondary (MEDIUM confidence)
- BlackHole GitHub README — device naming convention, `brew install blackhole-2ch`
- Yelp/detect-secrets v1.5.0 — baseline scan command

### Tertiary (LOW confidence)
- Brew install timing on macOS GHA runners (varies by runner state and caching)
- Exact `snd-aloop` device name string on `ubuntu-latest` (may be "Loopback: PCM" or "Loopback, Loopback PCM")

---

## Metadata

**Confidence breakdown:**
- GitHub Actions structure: HIGH — standard, well-documented
- snd-aloop + sounddevice integration: HIGH — kernel module is synchronous, sounddevice query_devices() is stable
- BlackHole detection: MEDIUM — name matching is empirical; "blackhole" substring is well-established
- Pre-commit hook versions: MEDIUM — pinned versions in examples may need updating at plan time
- Exact snd-aloop device name: LOW — empirical, check with `aplay -l` or `sd.query_devices()` on CI

**Research date:** 2026-02-20
**Valid until:** 2026-03-20 (stable domain; GitHub Actions action versions may update)
