---
phase: 08-ci-pipeline-with-virtual-audio-testing
plan: "01"
subsystem: testing
tags: [pytest, virtual-mic, conftest, sounddevice, snd-aloop, blackhole]

requires:
  - phase: 01-foundation
    provides: pytest infrastructure and conftest.py with --hardware pattern

provides:
  - --virtual-mic pytest flag with auto-skip logic for requires_virtual_mic marker
  - session-scoped virtual_mic_device fixture detecting snd-aloop (Linux) and BlackHole (macOS)
  - requires_virtual_mic marker registered in pyproject.toml

affects: [ci, audio-pipeline-tests, virtual-mic]

tech-stack:
  added: []
  patterns:
    - "--virtual-mic flag mirrors --hardware flag pattern in conftest.py"
    - "virtual_mic_device fixture uses sounddevice.query_devices() for cross-platform device detection"

key-files:
  created: []
  modified:
    - tests/conftest.py
    - pyproject.toml

key-decisions:
  - "Used session scope for virtual_mic_device fixture to avoid device enumeration per-test"
  - "Device detection by name substring ('loopback' on Linux, 'blackhole' on macOS)"
  - "Added type: ignore[no-untyped-call] for sounddevice.query_devices() which has no type stubs"
  - "Rewrote pytest_collection_modifyitems to handle both --hardware and --virtual-mic (removed early return pattern)"

patterns-established:
  - "requires_virtual_mic marker: use @pytest.mark.requires_virtual_mic for tests needing virtual mic"
  - "virtual_mic_device fixture: session-scoped, skips if no device found"

requirements-completed:
  - CI-INFRA

duration: 15min
completed: 2026-02-20
---

# Plan 08-01 Summary

**pytest --virtual-mic flag, requires_virtual_mic marker skip logic, and session-scoped virtual_mic_device fixture detecting snd-aloop (Linux) and BlackHole (macOS) via sounddevice.query_devices()**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-02-20
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added --virtual-mic addoption to conftest.py (mirrors --hardware pattern)
- Added requires_virtual_mic skip logic in pytest_collection_modifyitems
- Added session-scoped virtual_mic_device fixture with Linux (snd-aloop) and macOS (BlackHole) detection
- Registered requires_virtual_mic marker in pyproject.toml to suppress PytestUnknownMarkWarning

## Task Commits

1. **Task 1+2: conftest.py + pyproject.toml** - `52107d8` (feat: add --virtual-mic flag, requires_virtual_mic marker, and virtual_mic_device fixture)

## Files Created/Modified
- `tests/conftest.py` - Extended with --virtual-mic flag, marker skip logic, virtual_mic_device fixture
- `pyproject.toml` - Added requires_virtual_mic to markers list

## Decisions Made
- Rewrote pytest_collection_modifyitems: removed early return for --hardware, handle both flags independently
- Used session scope for virtual_mic_device to enumerate devices once per test run
- Device detection by name substring match (not index) for robustness across different runner configurations

## Deviations from Plan
None — plan executed as specified with one minor adaptation: added `_ = request` to satisfy the session fixture signature without unused variable warning.

## Issues Encountered
- sounddevice.query_devices() is untyped — added `# type: ignore[no-untyped-call]` per existing project pattern
- ruff B007: loop variable `i` unused in macOS branch — renamed to `_i`
- Several E501 line-too-long violations in help strings — wrapped with implicit string concatenation

## Next Phase Readiness
- virtual_mic_device fixture ready for audio pipeline tests to use with @pytest.mark.requires_virtual_mic
- CI workflow (08-03) can now run `pytest --virtual-mic` and tests will execute or skip appropriately

---
*Phase: 08-ci-pipeline-with-virtual-audio-testing*
*Completed: 2026-02-20*
