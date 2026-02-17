# Feature Research

**Domain:** System-wide voice dictation daemon (Linux Wayland)
**Researched:** 2026-02-17
**Confidence:** MEDIUM-HIGH — Table stakes and UX patterns drawn from multiple competitors; testing patterns from official docs and established Python tooling.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or the tool is unusable for daily work.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Reliable hotkey detection | Core interaction — if hotkey misses events the tool is broken | LOW | Already implemented via evdev. Needs robustness testing for edge cases (held keys, repeat events, modifier-only chords). |
| Text appears at cursor | The fundamental promise of the tool | LOW | Already implemented. Needs buffered-mode alternative for apps that drop characters during streaming injection. |
| Audio start/stop feedback | Users need to know the mic is active; no indicator = uncertainty, double-activations | LOW | Already implemented (beeps). Needs to survive PyAudio device errors gracefully. |
| Graceful error on service down | ydotoold not running should produce a clear error, not a silent failure | LOW | Already partially handled. Needs desktop notification + clear log message. |
| Automatic reconnection on drop | WebSocket disconnects happen; tool must self-heal without restart | MEDIUM | Not yet implemented. Standard pattern: exponential backoff (1s → 2s → 4s → max 30s + jitter). Critical for daily driver use. |
| Config file hot-reloading or clear first-run UX | Users need a way to configure hotkey/API key without reading source | LOW | Layered config exists. Needs documented first-run experience and `--config` flag. |
| Accurate transcription (95%+) | Voice dictation below ~95% accuracy is frustrating to use | LOW | Delegated to AssemblyAI. Already at ~97%. Not a code problem. |
| Graceful shutdown | Ctrl+C must stop cleanly — mic closed, WebSocket disconnected, no zombie threads | LOW | Already implemented. Needs validation under rapid start/stop cycling. |
| Push-to-talk AND toggle modes | Different users need different workflows; missing one alienates a group | LOW | Already implemented. |
| Trailing space after injection | Text following a dictated sentence should not collide with the next character | LOW | Already implemented as configurable option. |

### Differentiators (Competitive Advantage)

Features that set Murmur apart. Not required to function, but high user value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Buffered injection mode | Inject full turn at once on hotkey release rather than streaming partials. Prevents partial text appearing in apps that process keystrokes in batches (terminals, IDEs with autocomplete). | MEDIUM | Accumulate `_all_text_this_session` and inject on `stop()`. Toggle via config. Competitors (waystt, hyprwhspr) typically don't offer both modes. |
| System tray icon with live recording state | Visual confirmation of recording state without audio. Critical for silent environments, multi-monitor setups, screen recordings. Three states: idle, listening, error. | MEDIUM | pystray works on GTK-based Wayland compositors (GNOME via AppIndicator extension, KDE). Fails silently on GNOME without the extension — must handle gracefully. RED: recording, GREY: idle, AMBER: error. |
| Desktop error notifications | Surface actionable errors to the user without them watching logs. "ydotoold not running — start with: systemctl --user start ydotool" beats a silent failure. | LOW | Use `notify-send` subprocess (zero deps) or `desktop-notifier` library. Fallback to stderr if notification fails. |
| Session metrics logging | Audio duration, word count, latency per turn. Useful for power users tracking usage. | LOW | Trivially collected in transcriber callbacks. Write to `~/.local/share/murmur/sessions.jsonl`. |
| Partial transcript in log | Real-time words visible in `--log-level DEBUG` so users can see if mic is working without injecting text | LOW | Already partially implemented (`_on_partial` logs at DEBUG). |
| Systemd user service + auto-start | One-command setup for always-on dictation. Most competitors require manual launch. | LOW | Write a `.service` file + `systemctl --user enable murmur`. Requires RestartSec and Restart=on-failure. |
| Custom key delay tuning | Some apps (GTK apps, certain terminals) drop characters if injection is too fast. Per-app tuning is complex; global `key_delay` config handles 90% of cases. | LOW | Already implemented. Needs documentation with recommended values per app type. |
| `--dry-run` mode | Transcription runs but text is only logged, never injected. Safe for testing microphone and API key without polluting a document. | LOW | One flag check in `_on_final_transcript`. Extremely useful for first-time setup. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem valuable but create more problems than they solve at this stage.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Live partial text injection into cursor | Feels "real-time" and impressive | AssemblyAI v3 immutable transcripts means partials are often wrong — injecting them creates text that gets replaced/duplicated. Creates undo hell in editors with undo stacks. Users get confused when text changes under them. | Buffered injection: inject only finalized turns. Show partials in tray tooltip or log only. |
| Per-application hotkey profiles | "Use different hotkey in Firefox vs terminal" seems useful | Requires window focus detection via D-Bus/AT-SPI on Wayland — significant complexity, fragile across compositors, not supported in pure Wayland without portals. | Single global hotkey, document the toggle mode for use with window manager keybindings. |
| Voice commands ("delete that", "new paragraph") | Dragon NaturallySpeaking users expect this | Requires NLP on top of transcription, false-positive rate is high, heavily language/domain specific. Out of scope for a transcription relay tool. | Let the STT engine handle this if it supports it natively (AssemblyAI does not). |
| Built-in vocabulary training / custom models | Improves accuracy for domain-specific terms | Massively complex to implement; AssemblyAI's `custom_vocabulary` param in `StreamingParameters` already handles word boosting | Document the existing `custom_vocabulary` config option instead. |
| GUI settings panel | "Non-technical users need a UI" | Target users are developers and power users who run Python daemons. GUI adds a dependency (Qt/GTK), significant complexity, and a maintenance burden. Most Linux tools in this space are config-file driven. | Tray icon menu for toggle/quit only. Config via JSON file with documented schema. |
| Clipboard injection mode | Works around ydotool by pasting | Pollutes clipboard — user loses their clipboard content. Race conditions if user has copied something. Creates silent failures when clipboard manager is in use. | Fix ydotool reliability instead. Document `key_delay` for problematic apps. |
| Full offline-first architecture | Privacy appeal | local Whisper requires 1-4GB models, significant CPU/GPU resources, higher latency (300ms→1-3s), and complex VAD tuning. Massively out of scope for the reliability milestone. | Implement as a separate backend in Phase 3 (per VISION.md). The ABC makes this addable later without restructuring. |

---

## Feature Dependencies

```
[Reliable hotkey detection]
    └──requires──> [Correct evdev event filtering (modifiers + trigger)]
                       └──requires──> [Strict type annotations for event types]

[Automatic WebSocket reconnection]
    └──requires──> [Error callback from transcriber → orchestrator]
                       └──requires──> [Exponential backoff state machine in transcriber]
    └──enables──> [Session metrics logging (can count reconnects)]

[System tray icon]
    └──requires──> [Background thread running pystray event loop]
    └──requires──> [State machine: idle / recording / error]
    └──enhances──> [Desktop error notifications (tray provides a menu action)]

[Desktop error notifications]
    └──requires──> [Error classification (recoverable vs fatal)]
    └──enhances──> [Automatic reconnection (notify on reconnect attempt)]

[Buffered injection mode]
    └──requires──> [Session accumulator in transcriber (already partially implemented)]
    └──conflicts──> [Live partial injection (pick one per session)]

[Systemd user service]
    └──requires──> [Clean shutdown on SIGTERM (already implemented)]
    └──requires──> [Reliable restart behavior (no leaked file handles on crash)]

[--dry-run mode]
    └──requires──> [Config flag propagated to injector call site]
    └──enhances──> [First-run UX (safe way to test setup)]

[Session metrics logging]
    └──requires──> [TerminationEvent.audio_duration_seconds (already in SDK)]
    └──enhances──> [Tray tooltip showing session word count]
```

### Dependency Notes

- **Automatic reconnection requires error callback wiring:** The orchestrator must receive transcriber errors and decide whether to reconnect. Currently `_on_transcriber_error` only logs — it needs reconnection logic.
- **Tray icon conflicts with headless/SSH use:** Must check `DISPLAY`/`WAYLAND_DISPLAY` and disable gracefully if not available.
- **Buffered mode conflicts with live partial injection:** These are mutually exclusive within a session. Config determines which mode runs.
- **Strict typing enables testing:** Pyright strict mode makes it possible to write meaningful unit tests without runtime surprises — it is a prerequisite for reliable mocking patterns.

---

## MVP Definition

This milestone is brownfield (working prototype). MVP for this milestone = reliable enough to be a daily driver.

### Launch With (v1 — this milestone)

- [ ] **Automatic WebSocket reconnection with exponential backoff** — Without this, a transient network hiccup requires manual restart. Unacceptable for daily use.
- [ ] **Buffered injection mode** — Streaming partial injection causes character corruption in terminals and IDEs. Must be available as an opt-in config flag.
- [ ] **Desktop error notification for ydotoold not running** — Silent failure is the #1 user confusion point based on README troubleshooting section.
- [ ] **Graceful ydotoold crash recovery** — Attempt re-exec of ydotoold or log actionable message + notify. Don't crash silently.
- [ ] **Pyright strict mode compliance** — Required before adding tests; annotations prevent an entire class of threading bugs in callback paths.
- [ ] **pytest suite with mocked backends** — Unit tests for config loading, hotkey state machine, transcriber callbacks, injector. No hardware required in CI.
- [ ] **`--dry-run` flag** — Safe first-run validation without injecting garbage text into documents.

### Add After Validation (v1.x)

- [ ] **System tray icon** — High value, but pystray Wayland support is inconsistent. Implement after core reliability is proven; degrade gracefully if tray unavailable.
- [ ] **Session metrics logging** — Useful for power users, no dependencies. Add once the data pipeline is stable.
- [ ] **Systemd user service file** — Packaging concern; add once the daemon is stable enough to restart cleanly.

### Future Consideration (v2+)

- [ ] **Local Whisper backend** — Significant dependency (model weights, VAD, resource management). VISION.md Phase 3. Don't touch until cloud path is bulletproof.
- [ ] **Live transcript overlay (floating window)** — Requires a UI toolkit or Wayland protocol interaction. High complexity, niche use case for a system tray + audio feedback tool.
- [ ] **Per-application profiles** — Requires Wayland focus tracking. Not feasible without D-Bus/portal complexity.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Automatic WebSocket reconnection | HIGH | MEDIUM | P1 |
| Pyright strict mode + pytest suite | HIGH | MEDIUM | P1 |
| Buffered injection mode | HIGH | LOW | P1 |
| ydotoold crash recovery + notification | HIGH | LOW | P1 |
| `--dry-run` flag | MEDIUM | LOW | P1 |
| System tray icon (recording state) | HIGH | MEDIUM | P2 |
| Session metrics logging | LOW | LOW | P2 |
| Systemd user service file | MEDIUM | LOW | P2 |
| Custom key delay documentation | MEDIUM | LOW | P2 |
| Live transcript overlay | MEDIUM | HIGH | P3 |
| Per-application profiles | LOW | HIGH | P3 |
| Offline Whisper backend | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for reliability milestone launch
- P2: Should have, add when P1 items are stable
- P3: Nice to have, future milestone

---

## Competitor Feature Analysis

| Feature | waystt (minimal, Wayland) | hyprwhspr (Hyprland-focused) | VTT-Voice2Text (Windows) | Wispr Flow (macOS/Win, commercial) | Murmur (our approach) |
|---------|--------------------------|------------------------------|--------------------------|-------------------------------------|----------------------|
| Hotkey detection | Signal/keybind based | Super+Alt+D | F8/F9 global hotkey | Hold function key | evdev (Wayland-native) |
| Text injection | stdout piped to wtype | uinput/ydotool | direct injection | in-process API | ydotool (uinput) |
| Audio feedback | Yes (beep) | Yes (beep/boop) | No | No | Yes (PCM sine) |
| Reconnection | configurable retry | not documented | not documented | cloud-managed | NOT YET — build this |
| Tray icon | No | waybar integration | Yes (animated states) | Yes (microphone icon) | P2 target |
| Desktop notifications | No | journalctl only | No | No | P1 target (errors only) |
| Buffered injection | n/a (non-streaming) | n/a (non-streaming) | n/a (local, batch) | n/a (post-process) | P1 target |
| Live partial preview | No | No | floating overlay | No | log/debug only |
| Strict typing + tests | No | No | Not documented | n/a | P1 requirement |
| Offline capable | Yes (whisper.cpp) | Yes (Parakeet, Whisper) | Yes (faster-whisper) | No | Phase 3 |
| Systemd service | No | Yes | No | No | P2 target |

---

## Testing Patterns for Input/Audio Tools

Research finding: testing hardware-adjacent code (evdev, PyAudio, subprocess ydotool) requires a clear separation between unit tests (mocked) and integration tests (real hardware, optional).

### Recommended Pattern: Mock-First, Hardware-Optional

**Unit tests (always run, no hardware required):**
- Mock `evdev.InputDevice` and `evdev.categorize` to feed synthetic key events into `EvdevHotkeyListener`
- Mock `assemblyai.extras.MicrophoneStream` to feed synthetic audio frames to `AssemblyAITranscriber`
- Mock `subprocess.run` / `subprocess.Popen` to verify ydotool is called with correct arguments
- Use `pytest-mock` (`mocker.patch`) for all external boundaries
- Test callback wiring: assert `on_final` is called with expected text when mock transcriber fires events
- Test state machine: idle → recording → idle transitions, error → reconnect attempts

**Integration tests (opt-in, CI with hardware):**
- `umockdev` for evdev replay (record real keypress, replay in test)
- `pytest-subprocess` for subprocess verification without executing
- Environment variable `MURMUR_RUN_INTEGRATION=1` gates hardware tests

**Key insight from research:** PyAudio itself is hard to mock at the stream level — mock the `MicrophoneStream` class entirely rather than individual PyAudio calls. The AssemblyAI SDK owns the mic stream; the test boundary is at `StreamingClient.stream()`.

---

## Sources

- [waystt — Wayland Speech-to-Text Tool (GitHub)](https://github.com/sevos/waystt) — MEDIUM confidence
- [hyprwhspr — Native speech-to-text for Linux (GitHub)](https://github.com/goodroot/hyprwhspr) — MEDIUM confidence
- [VTT-Voice2Text — Windows voice dictation (GitHub)](https://github.com/hbiaou/vtt-voice2text) — MEDIUM confidence
- [Vocalinux — Offline Voice Dictation for Linux](https://vocalinux.com/) — MEDIUM confidence
- [Wispr Flow overview 2025](https://www.eesel.ai/blog/wispr-flow-overview) — MEDIUM confidence
- [RealtimeSTT library (GitHub)](https://github.com/KoljaB/RealtimeSTT) — MEDIUM confidence
- [pystray documentation — Wayland support notes](https://pystray.readthedocs.io/en/latest/faq.html) — MEDIUM confidence
- [desktop-notifier PyPI](https://pypi.org/project/desktop-notifier/) — LOW confidence (not verified against current version)
- [pytest-subprocess PyPI](https://pypi.org/project/pytest-subprocess/) — HIGH confidence (official PyPI)
- [umockdev — evdev replay for tests (GitHub)](https://github.com/martinpitt/umockdev) — MEDIUM confidence
- [WebSocket reconnection best practices 2026](https://oneuptime.com/blog/post/2026-01-27-websocket-reconnection-logic/view) — MEDIUM confidence
- [Top dictation tools December 2025 — Wispr Flow](https://wisprflow.ai/post/top-10-dictation-tools-december-2025) — LOW confidence (vendor source)

---
*Feature research for: system-wide voice dictation daemon (Linux Wayland)*
*Researched: 2026-02-17*
