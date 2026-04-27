---
status: resolved
trigger: "murmur daemon starts, pynput listener binds hotkeys successfully, but keypresses are never detected/received"
created: 2026-04-27T00:00:00Z
updated: 2026-04-27T15:00:00Z
---

## Current Focus

hypothesis: CONFIRMED - two bugs found and fixed
test: complete
expecting: hotkeys now fire correctly
next_action: archived

## Symptoms

expected: pressing hotkeys (e.g. Cmd+Ctrl+M, F12) should trigger push-to-talk or toggle dictation
actual: no hotkey callbacks fire - keypresses are completely ignored
errors: none at startup, bindings show as registered successfully
warnings: "Unknown destination {'kind': 'type'}"; defaulting to 'type'" x5 (before bindings logged)
reproduction: run `murmur daemon start`, press any bound hotkey - nothing happens
platform: macOS 26.2 (Tahoe), Darwin 25.2.0
started: unclear if ever worked

## Eliminated

- hypothesis: CGEventTap not created / IS_TRUSTED=False
  evidence: IS_TRUSTED=True confirmed, listener thread stays alive for 3+ seconds (RunLoop running)
  timestamp: 2026-04-27

- hypothesis: on_activate callback is None
  evidence: set_callbacks is called in DictationApp.__init__ before run()
  timestamp: 2026-04-27

- hypothesis: Binding matching logic fails
  evidence: direct _on_press(Key.f12, injected=False) call DOES activate correctly
  timestamp: 2026-04-27

- hypothesis: pystray NSApp interferes with CGEventTap
  evidence: CGEventTap is below AppKit level; pynput listener thread has its own RunLoop
  timestamp: 2026-04-27

## Evidence

- timestamp: 2026-04-27
  checked: config.json destination format
  found: destinations saved as {"kind": "type"} dicts by dataclasses.asdict()
  implication: _parse_destination calls str({"kind": "type"}) = "{'kind': 'type'}" -> warning x5, but TypeDestination() still returned

- timestamp: 2026-04-27
  checked: AXIsProcessTrusted() / IS_TRUSTED
  found: True - accessibility permission granted
  implication: CGEventTap creation succeeds

- timestamp: 2026-04-27
  checked: pynput listener thread lifetime
  found: is_alive() = True after 3 seconds with and without darwin_intercept
  implication: CGEventTap was created, RunLoop is spinning, listener is functional

- timestamp: 2026-04-27
  checked: murmur _on_press(Key.f12, injected=False) direct call
  found: ACTIVATED callback fires correctly
  implication: binding matching and callback chain work

- timestamp: 2026-04-27
  checked: murmur _on_press(Key.f12, injected=True) direct call
  found: callback does NOT fire (silently dropped by "if injected: return")
  implication: if physical keypresses arrive with injected=True, all events are silently dropped

- timestamp: 2026-04-27
  checked: pynput injected detection mechanism
  found: kCGEventSourceUnixProcessID != 0 -> injected=True
  implication: on macOS 26 (Tahoe), physical keyboard events may have non-zero UnixProcessID

- timestamp: 2026-04-27
  checked: murmur text injection via CGEventInjector
  found: uses CGEventCreateKeyboardEvent(source, 0, True) with vk=0 and no modifiers
  implication: injected text (vk=0, no Cmd/Ctrl) can NEVER match any configured hotkey binding

## Resolution

root_cause: TWO BUGS found:

  BUG 1 (PRIMARY - prevents all hotkey detection):
  murmur/hotkey/pynput.py _on_press() and _on_release() have "if injected: return" guards.
  pynput sets injected=True when kCGEventSourceUnixProcessID != 0.
  On macOS 26 (Tahoe), physical keyboard events may have a non-zero UnixProcessID
  (possibly from WindowServer or the new event subsystem), causing ALL physical keypresses
  to be silently dropped before any hotkey matching occurs.
  The guard is also unnecessary: murmur's own text injection uses vk=0 with no modifier keys,
  which cannot match any hotkey binding (which require Cmd+Ctrl combos or F12).

  BUG 2 (SECONDARY - causes 5 warnings per startup):
  config.save() uses dataclasses.asdict() which converts TypeDestination/ClipboardDestination
  to dicts like {"kind": "type"}. But _parse_destination in config.py calls
  str(bd.get("destination", "type")) which turns the dict into the STRING "{'kind': 'type'}",
  triggering the "Unknown destination" warning for every binding on reload.

fix:
  FIX 1: Removed "if injected: return" guards from _on_press() and _on_release()
          in murmur/hotkey/pynput.py. Updated docstrings to explain why.

  FIX 2: Added dict destination handling in _parse_destination() in murmur/config.py.
          When destination is a dict (from dataclasses.asdict()), the "kind" field is
          read directly to return the correct Destination type without any warning.

verification: All 133 tests pass. Direct testing confirms:
  - F12 with injected=True now fires callback (was silently dropped before)
  - Injected text character 'm' with no modifiers does NOT trigger Cmd+Ctrl+M binding
  - Config loads 5 bindings with NO "Unknown destination" warnings

files_changed:
  - murmur/hotkey/pynput.py: removed injected guards from _on_press and _on_release
  - murmur/config.py: added dict destination handling in _parse_destination
