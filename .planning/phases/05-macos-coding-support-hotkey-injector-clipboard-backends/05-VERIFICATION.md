---
phase: 05-macos-coding-support-hotkey-injector-clipboard-backends
verified: 2026-02-20T00:00:00Z
status: passed
score: 19/19 must-haves verified
---

# Phase 5: macOS Runtime Support Verification Report

**Phase Goal:** Add macOS runtime support at the code level — pynput hotkey backend, pynput+pbcopy injector backend, macOS clipboard backend, and macOS permission detection. No tooling, service files, or shell scripts. Linux behavior must be identical after the refactor.
**Verified:** 2026-02-20
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                 | Status     | Evidence |
|----|-----------------------------------------------------------------------|------------|----------|
| 1  | PynputHotkeyListener subclasses HotkeyListener ABC                   | VERIFIED   | `class PynputHotkeyListener(HotkeyListener):` at line 145 of `murmur/hotkey/pynput.py` |
| 2  | start() creates a fresh keyboard.Listener instance every call        | VERIFIED   | Lines 184-188: `self._listener = keyboard.Listener(...)` inside `start()`, after alive-check guard |
| 3  | stop() stops pynput listener and sets self._listener = None           | VERIFIED   | Lines 199-204: `self._listener.stop(); self._listener = None` |
| 4  | Ctrl+Alt+Space fires _dispatch_action via manual modifier-set tracking| VERIFIED   | `self._held` set maintained in `_on_press`/`_on_release`; `binding.modifiers.issubset(self._held)` at line 224; GlobalHotKeys not used anywhere in the file |
| 5  | Evdev key names translated to canonical pynput Keys at __init__ time  | VERIFIED   | `_resolve_bindings(bindings)` called in `__init__` at line 168; produces `_ResolvedBinding` with `frozenset` of canonical keys |
| 6  | listener.canonical(key) used before all set membership tests          | VERIFIED   | Lines 216-218 in `_on_press` and lines 244-246 in `_on_release`: `self._listener.canonical(key)` used before `self._held.add(canonical)` and all binding comparisons |
| 7  | PynputInjector subclasses TextInjector ABC                           | VERIFIED   | `class PynputInjector(TextInjector):` at line 45 of `murmur/injector/pynput.py` |
| 8  | inject() applies _sanitize_text, appends trailing space if configured, dispatches by inject_strategy | VERIFIED | Lines 73-94: sanitize called line 78, trailing space appended lines 82-83, strategy dispatch lines 85-94 |
| 9  | inject_backspaces(n) sends n individual backspace press+release via Controller | VERIFIED | Lines 124-132: `for _ in range(count): self._controller.press(keyboard.Key.backspace); self._controller.release(keyboard.Key.backspace)` |
| 10 | is_available() returns True if AXIsProcessTrusted() succeeds, True if ImportError | VERIFIED | Lines 62-71: `AXIsProcessTrusted()` returned directly; `except ImportError: return True` |
| 11 | copy_to_clipboard() calls pbcopy via subprocess.run with input=text.encode('utf-8') | VERIFIED | Lines 143-148: `subprocess.run(["pbcopy"], input=text.encode("utf-8"), ...)` |
| 12 | murmur/platform/__init__.py exists                                    | VERIFIED   | File exists at `murmur/platform/__init__.py` (2-line module-level docstring file) |
| 13 | check_accessibility() returns True if AXIsProcessTrusted() returns True, True if ImportError | VERIFIED | Lines 19-35 of `murmur/platform/macos.py`: `return bool(AXIsProcessTrusted())` and `except ImportError: return True` |
| 14 | check_microphone() returns True if authorized (3), warns-and-returns-True if notDetermined (0), False if denied/restricted | VERIFIED | Lines 38-70: status==3 returns True; status==0 logs warning and returns True; all other values (1=restricted, 2=denied) fall through to `return False` |
| 15 | On darwin with backend='auto', create_hotkey_listener returns PynputHotkeyListener | VERIFIED | Lines 38-44 of `murmur/hotkey/__init__.py`: `elif sys.platform == "darwin": from murmur.hotkey.pynput import PynputHotkeyListener; return PynputHotkeyListener(...)` |
| 16 | On darwin with backend='auto', create_injector returns PynputInjector | VERIFIED   | Lines 40-46 of `murmur/injector/__init__.py`: `elif sys.platform == "darwin": from murmur.injector.pynput import PynputInjector; return PynputInjector(...)` |
| 17 | pynput and pyobjc-framework-ApplicationServices added as darwin-only deps | VERIFIED | Lines 19-20 of `pyproject.toml`: `"pynput>=1.7.0; sys_platform == 'darwin'"` and `"pyobjc-framework-ApplicationServices>=9.0; sys_platform == 'darwin'"` |
| 18 | main.py checks Accessibility permission on darwin before starting hotkey listener | VERIFIED | Lines 237-245 of `murmur/main.py`: `if sys.platform == "darwin": from murmur.platform.macos import check_accessibility, check_microphone; if not check_accessibility(): fatal(...)` — called in `run()` before `self.hotkey.start()` at line 273 |
| 19 | Linux code paths unchanged (evdev and ydotool still the Linux backends) | VERIFIED  | `murmur/hotkey/evdev.py` and `murmur/injector/ydotool.py` unchanged; `hotkey/__init__.py` line 30 and `injector/__init__.py` line 31 still route `sys.platform == "linux"` to `EvdevHotkeyListener`/`YdotoolInjector` respectively |

**Score:** 19/19 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `murmur/hotkey/pynput.py` | PynputHotkeyListener backend | VERIFIED | 258 lines, substantive implementation with canonical key translation, modifier-set tracking, press/release dispatch |
| `murmur/injector/pynput.py` | PynputInjector backend | VERIFIED | 171 lines, three injection strategies (pynput/clipboard/clipboard-fallback), pbcopy integration |
| `murmur/platform/__init__.py` | Platform package marker | VERIFIED | Exists; minimal package init with module docstring |
| `murmur/platform/macos.py` | Permission detection helpers | VERIFIED | 71 lines; `check_accessibility()` and `check_microphone()` with full AVFoundation status mapping |
| `murmur/hotkey/__init__.py` | Factory with darwin routing | VERIFIED | darwin → PynputHotkeyListener; linux → EvdevHotkeyListener |
| `murmur/injector/__init__.py` | Factory with darwin routing | VERIFIED | darwin → PynputInjector; linux → YdotoolInjector |
| `pyproject.toml` | Darwin-only optional deps | VERIFIED | pynput and pyobjc-framework-ApplicationServices gated by `sys_platform == 'darwin'` |
| `murmur/main.py` | Platform permission guard | VERIFIED | darwin permission checks in `run()` before `hotkey.start()` |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `hotkey/__init__.py` | `hotkey/pynput.py` | lazy import in `auto`/`pynput` case | WIRED | `from murmur.hotkey.pynput import PynputHotkeyListener` inside match-case arm |
| `injector/__init__.py` | `injector/pynput.py` | lazy import in `auto`/`pynput` case | WIRED | `from murmur.injector.pynput import PynputInjector` inside match-case arm |
| `main.py` | `platform/macos.py` | import inside darwin guard | WIRED | `from murmur.platform.macos import check_accessibility, check_microphone` inside `if sys.platform == "darwin"` in `run()` |
| `hotkey/pynput.py` | `hotkey/base.py` | module-level import | WIRED | `from murmur.hotkey.base import HotkeyListener` at line 23; class inherits |
| `injector/pynput.py` | `injector/base.py` | module-level import | WIRED | `from murmur.injector.base import TextInjector` at line 21; class inherits |
| `PynputInjector.copy_to_clipboard` | pbcopy | subprocess.run | WIRED | `subprocess.run(["pbcopy"], input=text.encode("utf-8"), ...)` — no paste keystroke, clipboard-only |
| `PynputInjector._inject_via_clipboard` | pbcopy + Cmd+V | subprocess.run + controller.pressed | WIRED | pbcopy call followed by `with self._controller.pressed(keyboard.Key.cmd): self._controller.tap(KeyCode.from_char("v"))` |

---

## Requirements Coverage

No formal requirement IDs were assigned to phase 5. Verification performed against must-haves derived from the 4 PLAN.md files and the phase goal. All 19 must-haves verified — see Observable Truths table above.

---

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| None found | — | — | — |

No TODOs, FIXMEs, placeholder returns, empty implementations, or stub handlers found in the phase-5 files (`murmur/hotkey/pynput.py`, `murmur/injector/pynput.py`, `murmur/platform/macos.py`, `murmur/platform/__init__.py`).

---

## Human Verification Required

The following items cannot be verified programmatically. They require a macOS machine with the binary installed:

### 1. Accessibility permission prompt

**Test:** Run `murmur` on macOS without granting Accessibility permission.
**Expected:** Fatal error message with actionable System Settings path appears before any listener starts.
**Why human:** Cannot test AXIsProcessTrusted() return value or macOS permission dialogs without a real macOS process.

### 2. Ctrl+Alt+Space hotkey fires on macOS

**Test:** Configure `hotkey.bindings` with modifiers `[KEY_LEFTCTRL, KEY_LEFTALT]` and trigger `KEY_SPACE`, run murmur, press the combination.
**Expected:** Recording starts; releasing stops recording.
**Why human:** pynput modifier canonicalization and global keyboard listener behavior require a real macOS keyboard event stream.

### 3. pbcopy clipboard injection

**Test:** Use `copy_to_clipboard` action hotkey, speak, release.
**Expected:** Transcript text is on the macOS clipboard, pasteable with Cmd+V.
**Why human:** pbcopy + macOS clipboard requires real process and pasteboard access.

### 4. Microphone permission handling

**Test:** Run on macOS with microphone permission in notDetermined state.
**Expected:** Warning logged, murmur starts, system dialog appears on first audio capture.
**Why human:** AVFoundation status 0 (notDetermined) and the system dialog require real macOS runtime.

---

## Summary

All 19 must-haves verified against the actual codebase. The phase goal is fully achieved:

- **PynputHotkeyListener** is a complete, substantive implementation that subclasses the `HotkeyListener` ABC, performs evdev-to-pynput canonical key translation at init time, maintains a `_held` modifier set, uses `listener.canonical()` before all set membership tests, and dispatches via `_dispatch_action` on every matching press. GlobalHotKeys is not used anywhere.
- **PynputInjector** is a complete implementation subclassing `TextInjector` ABC, with all three injection strategies, `_sanitize_text` applied in both `inject()` and `inject_raw()`, `inject_backspaces()` using individual press+release per keystroke, and `copy_to_clipboard()` using `pbcopy` with UTF-8 encoded bytes.
- **murmur/platform/macos.py** provides `check_accessibility()` and `check_microphone()` with correct pyobjc AVFoundation status code mapping (0/1/2/3) and safe ImportError fallbacks.
- **Factory routing** in `hotkey/__init__.py` and `injector/__init__.py` correctly dispatches darwin to pynput backends and linux to evdev/ydotool backends; Linux paths are structurally unchanged.
- **pyproject.toml** correctly gates pynput and pyobjc-framework-ApplicationServices behind `sys_platform == 'darwin'`.
- **main.py** runs `check_accessibility()` and `check_microphone()` inside `run()` before `hotkey.start()`, gated by `sys.platform == "darwin"`.

---

_Verified: 2026-02-20_
_Verifier: Claude (gsd-verifier)_
