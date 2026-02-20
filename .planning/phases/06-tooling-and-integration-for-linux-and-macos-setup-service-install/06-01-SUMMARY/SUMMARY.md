# Plan 06-01 Summary: Service Tooling Refactor

**Status:** Complete
**Completed:** 2026-02-20
**Commit:** 84a1371

## What Was Built

Replaced the fragile hardcoded-path approach in the service installation tooling with a clean `@@MURMUR_DIR@@` placeholder token, and added macOS LaunchAgent support.

## Key Files

### key-files.modified
- `murmur.service` — replaced hardcoded `%h/dev/python/murmur` with `@@MURMUR_DIR@@` placeholder in both Documentation and ExecStart fields
- `install-service.sh` — rewrote with OS detection; clean `sed` substitution of `@@MURMUR_DIR@@`; added macOS branch using `launchctl load`

### key-files.created
- `murmur.plist` — macOS LaunchAgent template with `@@MURMUR_DIR@@` placeholder; `com.murmur.daemon` label; `RunAtLoad: true`; `KeepAlive.SuccessfulExit: false` (restart on crash, not clean exit)

## Tasks Completed

| Task | Description | Status |
|------|-------------|--------|
| 06-01-01 | Fix murmur.service — @@MURMUR_DIR@@ placeholder | ✓ |
| 06-01-02 | Create murmur.plist — macOS LaunchAgent template | ✓ |
| 06-01-03 | Overhaul install-service.sh — clean substitution + macOS branch | ✓ |

## Deviations

None. Implementation matched plan spec exactly.

## Self-Check: PASSED

- murmur.service: no hardcoded paths ✓
- murmur.plist: created with correct LaunchAgent structure ✓
- install-service.sh: Linux and Darwin branches both present ✓
- @@MURMUR_DIR@@ placeholder in all template files ✓
