# Pitfalls Research

**Domain:** Linux system-wide voice dictation (Wayland/evdev/ydotool/AssemblyAI/PyAudio)
**Researched:** 2026-02-17
**Confidence:** MEDIUM-HIGH (multiple sources; some claims verified against official docs and GitHub issues)

---

## Critical Pitfalls

### Pitfall 1: ydotoold Socket Permission Mismatch

**What goes wrong:**
When `ydotoold` runs as root (or under a system service started as root), it creates `/tmp/.ydotool_socket` with mode 600 (owner-only). The user process running murmur — even if in the `input` group — gets "connection refused" or "permission denied" on the socket, even though `/dev/uinput` itself is accessible.

**Why it happens:**
The socket owner/permission model is separate from the uinput device permission model. `ydotoold` defaults to socket perms of 0600. The systemd system service runs as root, creating a root-owned socket the user cannot write to.

**How to avoid:**
Run `ydotoold` as the local user (not root): `systemctl --user start ydotool`. Or, if running as root, start with `ydotoold --socket-perm 0660` so group members can connect. The `YDOTOOL_SOCKET` environment variable must also match between `ydotoold` and `ydotool`. Verify with: `stat /tmp/.ydotool_socket` — socket permissions should be at minimum `srw-rw----` with the correct group.

**Warning signs:**
- `ydotool type "test"` exits with "failed to connect socket `/run/user/1000/.ydotool_socket': No such file or directory"
- Socket exists under `/tmp/` but ydotool looks under `/run/user/$UID/`
- `is_available()` returns False despite `ydotoold` appearing to run (`pgrep ydotoold` returns a PID)

**Phase to address:** Reliability & Polish — daemon health-check and setup validation

---

### Pitfall 2: ydotool type Silently Drops Non-ASCII / Unicode Characters

**What goes wrong:**
`ydotool type` only handles basic Latin characters reliably. Accented characters (é, ü, ñ), curly quotes, em-dashes, and non-Latin scripts either produce wrong output or produce nothing at all. AssemblyAI's formatter routinely produces these: curly quotes around dialogue, em-dashes, accented proper nouns.

**Why it happens:**
ydotool maps characters to Linux input event key codes. Characters outside the basic Latin keyboard layout lack direct keycodes and the current `type` implementation has a known bug (confirmed in ydotool issue #249, still unfixed as of v1.0.4) where non-ASCII characters are silently dropped.

**How to avoid:**
Two approaches:
1. **Clipboard injection fallback**: For text containing non-ASCII, write to clipboard (`wl-copy`) and paste with `ydotool key ctrl+v`. This handles all Unicode but changes clipboard state.
2. **Strip/transliterate**: Apply pre-injection normalization to transliterate accented characters to ASCII equivalents before passing to ydotool (lossy but reliable).

The clipboard approach is preferred for dictation since text is being generated fresh. Add a detection step: if `text.isascii()` is False, use clipboard injection path.

**Warning signs:**
- Injected text appears shortened compared to logged text
- Characters like `"`, `"`, `—` vanish in the target application
- Words with accents (à, è, ö) output only the base letter or nothing

**Phase to address:** Reliability & Polish — buffered injection mode should implement clipboard fallback for non-ASCII

---

### Pitfall 3: evdev Grab Steals Input from Compositor

**What goes wrong:**
Calling `dev.grab()` on a keyboard input device makes the process the *exclusive* consumer of all keyboard events. The compositor (GNOME, KDE, Sway) receives nothing — the user cannot type, switch applications, or use any keyboard shortcut until the process releases the grab or crashes.

**Why it happens:**
`grab()` is the correct API for remapping tools that need to suppress the original keystrokes (e.g., key remappers). For dictation hotkey detection, you only need to *observe* events, not consume them. The grab/ungrab distinction is subtle and the evdev tutorial shows both without emphasizing the danger.

**How to avoid:**
Never call `dev.grab()` in murmur's hotkey listener. The current `evdev_listener.py` is correct — it explicitly comments `# NOTE: do NOT grab()`. Enforce this in code review. If a future developer "optimizes" by grabbing to reduce event processing load, it will render the keyboard unusable.

**Warning signs:**
- After starting murmur, all keyboard input to other applications stops
- Only murmur responds to keypresses
- Closing murmur restores keyboard to normal

**Phase to address:** Foundation (already addressed) — add test or assertion verifying grab is not called

---

### Pitfall 4: evdev Key-Release State Desync After Device Disconnect/Reconnect

**What goes wrong:**
The `_held_keys` set tracks which modifier keys are currently down. If a keyboard device disconnects mid-keystroke (USB unplug, Bluetooth drop, suspend/resume), the key-release event is never delivered. `_held_keys` remains `{KEY_LEFTCTRL, KEY_LEFTSHIFT}` indefinitely. The next hotkey detection fires on any `KEY_SPACE` press — even without modifiers held — because the modifier set is still "populated" from before the disconnect.

**Why it happens:**
The kernel delivers a disconnect as an `OSError` on read, not as key-up events for held keys. The current `_listen_loop` handles disconnect with `logger.warning` and stops processing that device, but does not flush `_held_keys`.

**How to avoid:**
On any `OSError` from `device.read()`, clear `_held_keys` and call `_handle_hotkey_release()` if recording was in progress. After clearing, attempt device reconnection by re-scanning `find_keyboard_devices()` every few seconds (with backoff). For Bluetooth keyboards specifically, disconnects during suspend are routine.

**Warning signs:**
- After unplugging/replugging a keyboard, dictation triggers on a bare spacebar press
- Toggle mode never un-toggles after a suspend/resume cycle
- `_held_keys` is non-empty when no keys are physically pressed

**Phase to address:** Reliability & Polish — hotkey listener must flush held-key state on device disconnect

---

### Pitfall 5: AssemblyAI Session Expires Without Reconnection (3-Hour Limit + Error 3005)

**What goes wrong:**
AssemblyAI streaming sessions have a maximum duration (default 10800 seconds / 3 hours, but also closable with error 3005 for audio rate violations or inactivity). When the session closes, the `StreamingClient` fires the `Error` callback and disconnects. Without explicit reconnection logic, subsequent hotkey presses open a fresh streaming session — but if the client object is in an error state, `start()` will throw or silently produce no transcripts.

**Why it happens:**
The current `AssemblyAITranscriber` creates a new `StreamingClient` on each `start()` call, which is the right pattern — but if the client is in a broken state from a previous error (e.g., disconnect during `stop()`), re-creating it without resetting state can leave `_is_streaming` true while no actual connection exists.

**How to avoid:**
- In the `Error` handler: set `_is_streaming = False` and nullify `_client`
- In `start()`: assert `_client is None` before creating a new one
- Implement exponential backoff retry for connection errors (not auth errors — error 1008 means bad API key or billing, no point retrying)
- Distinguish error codes: 3005 = retry with backoff, 1008 = surface to user and abort
- Log session ID from `BeginEvent` so errors are diagnosable

**Warning signs:**
- Hotkey press produces no transcription and no error log
- `_is_streaming` is True but no `TurnEvent` callbacks fire
- `StreamingError` logged once, then silence

**Phase to address:** Reliability & Polish — automatic reconnection and error classification

---

### Pitfall 6: PyAudio Opens Wrong Microphone (Default Device Mismatch)

**What goes wrong:**
`aai.extras.MicrophoneStream()` opens the PortAudio default input device, which may differ from the PulseAudio/PipeWire default. On systems with multiple input devices (USB headset, built-in mic, virtual devices), PortAudio may select a different device than what the user configured in their desktop sound settings.

**Why it happens:**
PortAudio's "default" device is resolved by the ALSA layer, which may not honor PulseAudio/PipeWire routing preferences. On PipeWire systems, `pw-cli` or `wpctl` manages the default, but PortAudio queries ALSA's default directly. The result: user sees the correct mic in GNOME Settings but murmur captures from a different (often wrong or silent) source.

**How to avoid:**
- Expose a `device_index` config option for `MicrophoneStream`
- On startup, log the device name being opened: `pa.get_device_info_by_index(device_index)['name']`
- Consider using the PulseAudio/PipeWire virtual device name ("default") instead of index 0
- The AssemblyAI SDK's `MicrophoneStream` accepts a `device_index` parameter — thread it through from config

**Warning signs:**
- Good audio quality in system settings, poor or silent transcription
- ALSA lib error messages about "pcm" or "plugin" in stderr
- Transcription works on reboot but not after changing audio devices

**Phase to address:** Reliability & Polish — device selection config; also relevant to Phase 4 (UX) for device picker

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `subprocess.run(["ydotool", ...])` on each injection | Simple, no state management | One subprocess per injection; cumulative latency on rapid speech; no socket pooling | Acceptable for now; revisit if injection latency > 100ms in practice |
| `pgrep -x ydotoold` to check daemon | Easy availability check | Doesn't verify socket connectivity; daemon may run but socket unreachable | Acceptable in MVP; replace with actual socket connect test in Reliability phase |
| Single-threaded `_stream_audio` with `client.stream(mic)` blocking | Simple lifecycle | If AssemblyAI SDK hangs on `stream()`, the thread blocks indefinitely; `stop()` must kill the thread externally | Acceptable now; add join timeout and force-kill in Reliability phase |
| No explicit audio device selection | Zero config for common case | Fails silently on multi-device setups; breaks on USB headset hot-plug | Never acceptable for release; add `device_index` config in Phase 2 |
| `_held_keys` without disconnect flush | Minimal code | Phantom modifier state after device disconnect triggers spurious dictation | Never acceptable; fix in Reliability phase |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| ydotoold daemon | Assuming daemon runs as system service (root) | Run as user service: `systemctl --user enable --now ydotool`; set `YDOTOOL_SOCKET=/run/user/$UID/.ydotool_socket` |
| AssemblyAI SDK v3 | Using `disconnect()` without `terminate=True` | Use `disconnect(terminate=True)` to signal server to finalize session; bare disconnect leaves session open server-side, consuming minutes |
| AssemblyAI error 3005 | Treating as transient network error | 3005 is a protocol/validation error (audio rate too fast, or session duration exceeded) — don't retry audio rate violations, do retry network drops |
| PyAudio on PipeWire | Relying on PortAudio "default" device index | PipeWire's PulseAudio compat layer often works but ALSA default may still differ; test explicitly on PipeWire systems |
| evdev with multiple keyboards | Opening only the first detected keyboard | USB hub keyboards, Bluetooth keyboards, and virtual keyboards each appear as separate `/dev/input/eventN` devices; open all detected ones |
| ydotool `--clearmodifiers` | Assuming it works universally | `--clearmodifiers` is ydotool's flag (it exists) but behavior depends on compositor; if held modifiers still interfere, add a configurable `pre_injection_delay_ms` to allow modifier keys to register as released |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Subprocess per injection with long text | Latency spikes > 500ms for long turns (sentences > 50 words) | Batch or pipeline injection; consider `wtype` or direct uinput write for large blocks | Immediately noticeable on fast speakers or long sentences |
| Audio buffer accumulation without backpressure | RAM grows unboundedly during a long dictation session; eventual OOM | `MicrophoneStream` buffers should drain promptly; avoid storing raw PCM in Python memory | On sessions > 30 minutes of continuous dictation |
| Thread proliferation from repeated start/stop | `threading.active_count()` grows over time; eventually Python GIL contention | Reuse threads via `threading.Event` signaling; don't create new threads per hotkey press | After dozens of start/stop cycles |
| Selector timeout too short (< 50ms) | CPU spikes to 100% in the evdev listener thread | Keep timeout at 100ms (current default); selector.select() with short timeout is busy-poll | Immediately — CPU visible in `top` |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing API key in config.json in world-readable location | API key exposure via `~/.config/dictation/config.json`; other local users can read it | Set `config.json` mode to 0600 on creation: `CONFIG_FILE.chmod(0o600)` after writing |
| Using `ASSEMBLYAI_API_KEY` in process environment (visible in `/proc/PID/environ`) | Local users with `/proc` access can read env of running process | Risk is low on single-user desktops; acceptable. For shared systems, use a keyring |
| `grab()` without exception handling | If process crashes mid-grab, keyboard is dead until device is closed | The process should re-register SIGTERM/SIGKILL handlers to ensure cleanup; avoid grab() entirely for monitoring use cases |
| Running murmur or ydotoold as root | Root process can read all input events (keylogger-level access) and inject arbitrary input | Always run as unprivileged user with only the `input` group membership required |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No feedback when ydotoold is not running | User presses hotkey, speaks, nothing happens; silent failure | Check `is_available()` at startup AND on each activation; send desktop notification via `notify-send` if daemon is missing |
| Injecting text while focus has shifted | If user releases hotkey and focuses a different field in < 300ms, text lands in wrong field | Accept this as a hard problem; document it; consider injecting only on hotkey release (buffered mode) so user can verify focus |
| Long sentences injected as one burst | Some apps (terminal emulators, certain web inputs) drop characters at high keystroke rates | Use `--key-delay 12` (ydotool default) and expose tuning parameter; add config guidance for terminals |
| Tray icon required but missing on pure Wayland GNOME | User sees no recording indicator; has no way to know murmur is running | Do not require tray icon as primary UI; use desktop notifications as fallback; treat tray as optional progressive enhancement requiring AppIndicator extension |
| Audio feedback beeps at wrong volume or missing | User can't tell if dictation is active | Beep should follow system volume; if PyAudio playback fails, log warning but do not crash |

---

## "Looks Done But Isn't" Checklist

- [ ] **evdev hotkey listener:** Handles device disconnect mid-session — verify `_held_keys` is cleared and recording stops cleanly
- [ ] **ydotool injector:** Tested with non-ASCII text (accented characters, curly quotes from AssemblyAI formatter) — verify characters are not silently dropped
- [ ] **AssemblyAI reconnection:** Error handler sets `_is_streaming = False` — verify second hotkey press after error creates a fresh working session
- [ ] **ydotoold socket path:** Murmur and ydotoold are using the same `YDOTOOL_SOCKET` path — verify with both system and user service configurations
- [ ] **Microphone device:** Log which device is opened at startup — verify it matches the system default in `wpctl status` or `pactl info`
- [ ] **Tray icon absent:** murmur degrades gracefully (notification-only feedback) when no SNI-supporting tray is available — verify on bare GNOME Wayland without AppIndicator extension
- [ ] **Config file permissions:** `~/.config/dictation/config.json` is created with mode 0600, not world-readable
- [ ] **Long session:** Test a 10+ minute continuous session — verify no thread leak, no memory growth, clean shutdown

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| ydotoold socket mismatch | LOW | `systemctl --user restart ydotool`; verify `YDOTOOL_SOCKET` env var; check `stat` on socket file |
| ydotool drops Unicode chars | MEDIUM | Switch injection path to clipboard: `wl-copy "$text" && ydotool key ctrl+v`; test on target app |
| evdev key-state desync | LOW | Restart murmur; the desync clears on process restart since `_held_keys` is re-initialized |
| AssemblyAI session error | LOW | murmur auto-retries if reconnection logic is implemented; otherwise restart process |
| Wrong microphone captured | LOW | Set `device_index` in config.json; restart murmur |
| Tray icon not visible | LOW | Install gnome-shell-extension-appindicator and enable it; tray icon appears on next murmur start |
| PyAudio "No Default Input Device" | MEDIUM | Check `pw-cli list-objects Node type=Audio/Source`; set explicit device_index in config; verify PipeWire/PulseAudio is running |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| ydotoold socket permission mismatch | Phase 2: Reliability | `ydotool type "test"` succeeds as normal user without sudo; `is_available()` returns True |
| ydotool drops non-ASCII chars | Phase 2: Reliability (buffered injection) | Inject "café résumé" — verify all chars appear correctly in target app |
| evdev grab steals input | Phase 1: Foundation (already addressed) | Start murmur; verify typing in another window still works |
| evdev key-state desync on disconnect | Phase 2: Reliability | Unplug keyboard while modifier held; reconnect; verify hotkey requires modifiers again |
| AssemblyAI session expiry / error 3005 | Phase 2: Reliability | Simulate network drop; verify murmur recovers and transcribes on next hotkey press |
| PyAudio wrong microphone | Phase 2: Reliability | Add `device_index` config; log device name at startup; verify matches system default |
| Tray icon absent on GNOME Wayland | Phase 4: UX | Test on stock GNOME Wayland (no extensions); verify fallback to `notify-send` works |
| Config file world-readable | Phase 5: Packaging | `stat ~/.config/dictation/config.json` shows `rw-------` (0600) |
| Character drops in terminals | Phase 2: Reliability | Test injection into gnome-terminal, kitty, alacritty with default key_delay; document recommended value |
| Non-ASCII via clipboard path | Phase 2: Reliability | Implement clipboard fallback; test with AssemblyAI's formatted output containing punctuation |

---

## Sources

- ydotool issue #249 — Unicode characters not printing: https://github.com/ReimuNotMoe/ydotool/issues/249
- ydotool issue #73 — Socket permissions: https://github.com/ReimuNotMoe/ydotool/issues/73
- ydotool issue #36 — ydotoold backend unavailable: https://github.com/ReimuNotMoe/ydotool/issues/36
- ydotool issue #161 — Address already in use: https://github.com/ReimuNotMoe/ydotool/issues/161
- ydotool issue #234 — Failed to open uinput device: https://github.com/ReimuNotMoe/ydotool/issues/234
- ydotool issue #5 — Strange behavior with --delay: https://github.com/ReimuNotMoe/ydotool/issues/5
- python-evdev issue #4 — Strange behavior of grab(): https://github.com/gvalkov/python-evdev/issues/4
- python-evdev issue #64 — Behavior of read() when device disappears: https://github.com/gvalkov/python-evdev/issues/64
- AssemblyAI common session errors: https://www.assemblyai.com/docs/universal-streaming/common-session-errors-and-closures
- pystray Wayland issue #174: https://github.com/moses-palmer/pystray/issues/174
- GNOME AppIndicator extension: https://extensions.gnome.org/extension/615/appindicator-support/
- Arch Linux Forums — ydotool setup: https://bbs.archlinux.org/viewtopic.php?id=284968
- Flatpak daemon packaging issue #524: https://github.com/flatpak/flatpak/issues/524

---
*Pitfalls research for: Linux system-wide voice dictation (Wayland/evdev/ydotool/AssemblyAI)*
*Researched: 2026-02-17*
