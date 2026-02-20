# Phase 8: CI Pipeline with Virtual Audio Testing - Context

**Gathered:** 2026-02-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Set up GitHub Actions CI (lint, type-check, unit tests, virtual-mic audio pipeline tests) and pre-commit hooks. Scope is CI infrastructure only — no release pipeline, no PyPI publish workflow.

</domain>

<decisions>
## Implementation Decisions

### CI platform and workflow
- GitHub Actions, single workflow file `ci.yml` triggering on push and pull_request
- Matrix: `ubuntu-latest` + `macos-latest`, Python `3.11` + `3.12`
- `astral-sh/setup-uv` for dependency installation (project already uses uv)
- Fail fast (default): cancel remaining matrix jobs when one fails

### What CI enforces
- `ruff check .` — linting
- `ruff format --check .` — formatting
- `pyright` — type checking
- `pytest` — unit tests (fully mocked, no hardware)
- `pytest --virtual-mic` — audio pipeline tests using virtual mic device
- `pre-commit run --all-files` — all pre-commit hooks

### Virtual mic — Linux
- `snd-aloop` (ALSA loopback kernel module): `sudo modprobe snd-aloop` in CI setup step
- Creates a virtual soundcard that sounddevice/PortAudio sees as a real ALSA input device
- `conftest.py` adds a `virtual_mic_device` fixture that yields the loopback device index/name
- Tests annotated `@pytest.mark.requires_virtual_mic` are skipped unless `--virtual-mic` flag passed

### Virtual mic — macOS
- BlackHole virtual audio driver: `brew install blackhole-2ch` in CI setup step
- Same `--virtual-mic` flag and fixture mechanism, fixture detects available virtual device by name
- Same `@pytest.mark.requires_virtual_mic` marker works on both platforms

### Test tier design
- `pytest` — unit only (always runs, fully mocked)
- `pytest --virtual-mic` — unit + audio pipeline (CI + local with snd-aloop/BlackHole loaded)
- `pytest --hardware` — everything including real-mic e2e (local only, existing flag)
- New flag `--virtual-mic` added to `conftest.py` alongside existing `--hardware`

### Pre-commit hooks
- `.pre-commit-config.yaml` added to repo root
- Hooks to include:
  - `ruff` — lint + format (via `astral-sh/ruff-pre-commit`)
  - `pyright` — type checking (via local env / `pre-commit` mirror)
  - `check-added-large-files` — reject files > 500 KB (pre-commit-hooks)
  - `detect-secrets` — scan for API keys, tokens, private keys
  - `check-jupyter` / `check-case-conflict` / forbid `.ipynb` files — pre-commit-hooks
  - `trailing-whitespace` + `end-of-file-fixer` — pre-commit-hooks
- CI runs `pre-commit run --all-files` as a separate step

### README badge
- Add GitHub Actions CI status badge to README.md once workflow is in place

### Claude's Discretion
- Exact `snd-aloop` device index discovery in the fixture
- BlackHole device name detection (e.g. partial match on "BlackHole")
- Whether pyright runs as a pre-commit hook or only directly in CI (pyright in pre-commit can be slow)
- `detect-secrets` baseline file handling

</decisions>

<specifics>
## Specific Ideas

- `--virtual-mic` flag mirrors the existing `--hardware` flag pattern already in `conftest.py`
- Virtual mic fixture should be a session-scoped pytest fixture so device is opened once per test run, not per test
- CI step order: setup virtual audio → install deps → pre-commit → lint/type-check → unit tests → virtual-mic tests

</specifics>

<deferred>
## Deferred Ideas

- Release pipeline (PyPI publish, auto-fill Homebrew SHA256, GitHub Release creation) — separate phase
- AssemblyAI API key in CI for mid-tier WebSocket tests — could be a future phase or added to the release phase
- Mock WebSocket server for testing AssemblyAI protocol without API credits — future phase

</deferred>

---

*Phase: 08-ci-pipeline-with-virtual-audio-testing*
*Context gathered: 2026-02-20*
