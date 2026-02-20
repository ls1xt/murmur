---
phase: 05-macos-coding-support-hotkey-injector-clipboard-backends
plan: "03"
subsystem: platform
tags: [macos, pyobjc, accessibility, microphone, permissions, avfoundation, applicationservices]

# Dependency graph
requires: []
provides:
  - "murmur/platform package with macOS permission detection"
  - "check_accessibility() via AXIsProcessTrusted for pynput keyboard listener"
  - "check_microphone() via AVFoundation authorization status for PyAudio"
affects:
  - "05-macos-coding-support-hotkey-injector-clipboard-backends"
  - "06-tooling-and-integration-for-linux-and-macos-setup-service-install"

# Tech tracking
tech-stack:
  added: [pyobjc-framework-ApplicationServices (optional), pyobjc-framework-AVFoundation (optional)]
  patterns:
    - "try/except ImportError around all platform-specific framework imports -- safe cross-platform import"
    - "Graceful degradation: log warning and return True when pyobjc unavailable"
    - "macOS permission checks at daemon startup -- mirrors Linux ydotoold check pattern"

key-files:
  created:
    - murmur/platform/__init__.py
    - murmur/platform/macos.py
  modified: []

key-decisions:
  - "All macOS framework imports (ApplicationServices, AVFoundation) are gated inside function bodies with try/except ImportError -- ensures importable on Linux without crashing"
  - "notDetermined microphone status (0) returns True and logs warning -- lets PyAudio trigger system dialog on first use rather than failing at startup"
  - "ImportError fallback returns True (not False) -- cannot verify permission, assume ok, let actual runtime fail if missing"

patterns-established:
  - "Platform subpackage pattern: murmur/platform/<os>.py with guarded imports for OS-specific checks"

requirements-completed: []

# Metrics
duration: 4min
completed: 2026-02-20
---

# Phase 05 Plan 03: macOS Permission Detection Summary

**macOS Accessibility and Microphone permission checks via pyobjc (AXIsProcessTrusted + AVFoundation), safely importable on Linux with graceful fallback**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-02-20T10:14:31Z
- **Completed:** 2026-02-20T10:18:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Created `murmur/platform/` subpackage with empty package marker docstring
- Implemented `check_accessibility()` using `AXIsProcessTrusted()` from pyobjc-framework-ApplicationServices
- Implemented `check_microphone()` using `AVCaptureDevice.authorizationStatusForMediaType_()` from pyobjc-framework-AVFoundation
- Both functions are importable and functional on Linux (graceful ImportError fallback returns True with warning log)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create murmur/platform package with macOS permission checks** - `b39d045` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `murmur/platform/__init__.py` - Package marker with docstring "Platform-specific runtime helpers."
- `murmur/platform/macos.py` - check_accessibility() and check_microphone() with pyobjc imports guarded inside function bodies

## Decisions Made
- All macOS framework imports placed inside `try/except ImportError` blocks within function bodies, not at module level -- allows Linux import without crashing and safe use in tests
- Microphone notDetermined status (0) treated as True with warning -- avoids blocking startup, lets PyAudio trigger the OS dialog on first use
- ImportError fallback returns True -- conservatively allows startup when pyobjc unavailable; runtime failure is more informative than a premature startup block

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. pyobjc packages are optional runtime dependencies; the module degrades gracefully when they are absent.

## Next Phase Readiness
- `murmur.platform.macos` is ready for import in macOS daemon startup (main.py or platform-specific entry points)
- Callers should invoke `check_accessibility()` and `check_microphone()` at startup on darwin and call `fatal()` if either returns False
- Linux is unaffected -- functions are unreachable via normal code paths on Linux but safe to import

---
*Phase: 05-macos-coding-support-hotkey-injector-clipboard-backends*
*Completed: 2026-02-20*
