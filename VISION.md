# Murmur — Project Vision

*System-wide voice dictation for people who think faster than they type.*

---

## What Is Murmur?

Murmur is a lightweight, always-ready dictation tool that lives at the OS level. Hold a hotkey, speak, release — your words appear at the cursor in whatever application you're using. Browser, terminal, text editor, Slack, email — it doesn't matter. Murmur injects transcribed speech as simulated keystrokes, indistinguishable from physical typing.

It targets Linux (Wayland-first) and macOS, the two platforms where no good system-wide dictation story exists today. Windows has built-in dictation; Linux and macOS users are left cobbling together partial solutions or relying on per-application integrations. Murmur fills that gap with a single, focused tool.

## The Problem

Voice input on desktop is fragmented and frustrating:

- **Linux/Wayland has nothing.** Wayland's security model intentionally blocks the techniques (X11 input simulation, clipboard injection) that older dictation tools relied on. Most existing tools simply don't work. The few that do require X11 or XWayland, limiting them to a subset of applications.
- **macOS dictation is mediocre.** Apple's built-in dictation exists but is tightly coupled to Apple's own speech engine, offers no customization, and can't be replaced with a better model without replacing the entire input pipeline.
- **Cloud STT APIs are excellent but disconnected.** Services like AssemblyAI deliver stunning accuracy with sub-300ms latency — but there's no simple bridge from "audio in, text out" to "text appears where I'm typing."

The missing piece is the plumbing: a small daemon that captures audio on hotkey, streams it to a high-quality STT engine, and injects the result at the kernel input level so every application receives it natively.

## Design Principles

**Invisible when idle, instant when needed.** Murmur should have zero cognitive overhead. Press the key, talk, release. No window to focus, no mode to remember, no UI to navigate. It should feel like your keyboard briefly gained the ability to understand speech.

**Wayland-native, not Wayland-compatible.** Rather than fighting Wayland through XWayland shims, Murmur works *with* the security model by using kernel-level input (`uinput` via ydotool/dotool) for text injection and `evdev` for hotkey detection. These are the same mechanisms Wayland compositors themselves use.

**Pluggable at every layer.** The hotkey listener, speech engine, and text injector are independent components behind abstract interfaces. Swap AssemblyAI for local Whisper when you need offline mode. Replace ydotool with wtype on wlroots compositors. Add a new hotkey backend for a niche input device. Each piece is replaceable without touching the others.

**Cloud-first, offline-ready.** The default path uses AssemblyAI's Universal-Streaming for best-in-class accuracy and latency. But the architecture doesn't assume a network connection — a local Whisper backend slots in through the same `Transcriber` interface.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        DictationApp                          │
│               (main.py — orchestrator)                       │
│                                                              │
│  ┌─────────────┐   ┌──────────────┐   ┌─────────────────┐   │
│  │   Hotkey     │──▶│  Transcriber │──▶│   Injector       │   │
│  │  Listener    │   │  (STT)       │   │  (typing)        │   │
│  └─────────────┘   └──────────────┘   └─────────────────┘   │
│        │                   │                    │             │
│        ▼                   ▼                    ▼             │
│  ┌─────────────┐   ┌──────────────┐   ┌─────────────────┐   │
│  │ evdev       │   │ AssemblyAI   │   │ ydotool         │   │
│  │ (Wayland)   │   │ Universal    │   │ (uinput)        │   │
│  ├─────────────┤   │ Streaming v3 │   ├─────────────────┤   │
│  │ pynput      │   ├──────────────┤   │ pynput          │   │
│  │ (macOS/X11) │   │ (Whisper)    │   │ (macOS/X11)     │   │
│  └─────────────┘   │ (future)     │   ├─────────────────┤   │
│                     └──────────────┘   │ dotool / wtype  │   │
│                                        │ (future)        │   │
│  ┌────────────────────────────────┐    └─────────────────┘   │
│  │         AudioFeedback          │                          │
│  │   (start/stop beep via PyAudio)│                          │
│  └────────────────────────────────┘                          │
└──────────────────────────────────────────────────────────────┘
```

Every box with multiple rows is a concrete backend behind an abstract base class. The `DictationApp` orchestrator only knows about the ABCs.

### Component Responsibilities

| Component | ABC | Wayland Backend | macOS Backend |
|---|---|---|---|
| **Hotkey Listener** | `HotkeyListener` | `EvdevHotkeyListener` — reads `/dev/input/event*` directly via `python-evdev`. Works on any display server. Requires `input` group. | `PynputHotkeyListener` — uses pynput's `keyboard.Listener`. Requires Accessibility permissions. |
| **Transcriber** | `Transcriber` | `AssemblyAITranscriber` — streams mic audio to AssemblyAI Universal-Streaming v3 over WebSocket. ~300ms latency, immutable transcripts, intelligent endpointing. | Same (cross-platform). |
| **Text Injector** | `TextInjector` | `YdotoolInjector` — simulates a virtual keyboard via kernel `uinput`. Bypasses Wayland's input isolation entirely. Requires `ydotoold` daemon + `input` group. | `PynputInjector` — uses pynput's `keyboard.Controller.type()`. Requires Accessibility permissions. |
| **Feedback** | — | `AudioFeedback` — generates PCM sine tones in-process, plays via PyAudio. No external sound files. | Same. |

### Data Flow (Push-to-Talk)

```
1. User holds Ctrl+Shift+Space
       │
       ▼
2. EvdevHotkeyListener detects modifier+trigger combo
       │
       ▼
3. DictationApp.on_activate() fires
       │
       ├──▶ AudioFeedback.play_start()    (beep)
       │
       └──▶ AssemblyAITranscriber.start()
              │
              ├── Opens MicrophoneStream (PyAudio, 16kHz PCM16)
              ├── Connects StreamingClient to wss://streaming.assemblyai.com/v3/ws
              └── Streams audio frames in real-time
                     │
                     ▼
              AssemblyAI returns TurnEvents:
                - Partial transcripts (words arriving in real-time)
                - End-of-turn with formatted text (punctuated, cased)
                     │
                     ▼
4. on_final_transcript("Hello, this is a test.")
       │
       ▼
5. YdotoolInjector.inject("Hello, this is a test. ")
       │  └── subprocess: ydotool type --clearmodifiers -- "Hello, this is a test. "
       │
       ▼
6. Text appears in focused application (browser, editor, terminal, anything)

7. User releases Ctrl+Shift+Space
       │
       ▼
8. DictationApp.on_deactivate() fires
       │
       ├──▶ AudioFeedback.play_stop()
       └──▶ AssemblyAITranscriber.stop()
              ├── Closes MicrophoneStream
              └── Disconnects WebSocket (terminate=True)
```

### Why These Technology Choices?

**evdev over pynput for Wayland hotkeys:** pynput's keyboard listener is fundamentally broken on Wayland (confirmed Feb 2025, GitHub issue #628). It falls back to XWayland, which only receives events from XWayland applications. evdev reads from the kernel input subsystem — it works regardless of display server, compositor, or application toolkit.

**ydotool over wtype/xdotool:** ydotool uses kernel `uinput` to create a virtual keyboard device. The compositor sees it as a real hardware keyboard. This works on Wayland, X11, and even virtual consoles. wtype only works on wlroots-based compositors (not GNOME/KDE). xdotool requires X11.

**AssemblyAI Universal-Streaming v3:** Immutable transcripts (text never rewrites), intelligent endpointing (knows when you've finished a thought), formatted output with punctuation/casing, and ~300ms P50 latency. The v3 SDK uses a clean event-based API (`StreamingClient` + `StreamingEvents`).

**`--clearmodifiers` on ydotool:** When the user is holding Ctrl+Shift+Space and a turn completes mid-dictation, ydotool would normally combine the held modifiers with the typed characters (producing Ctrl+Shift+H instead of "H"). The `--clearmodifiers` flag suppresses held modifiers during typing.

## Engineering Standards

Murmur is a small tool, but it's built with the rigor of production software. The codebase enforces **strict static typing via Pyright** in strict mode — every function signature is annotated, every return type is explicit, and `Any` is treated as a code smell. Tests live alongside the code they exercise, run via **pytest** with clear arrange/act/assert structure, and cover both unit behavior (mocked backends) and integration paths (real evdev/ydotool on CI where available). The architecture follows **DRY** religiously: each decision about platform detection, key mapping, and audio format lives in exactly one place. **KISS** governs the API surface — each ABC has two or three methods, factories take a config dataclass and return a ready-to-use object, and the orchestrator is a single class with a linear lifecycle. Configuration uses **dataclasses with sensible defaults**, layered with environment variable overrides, so the common case (`export ASSEMBLYAI_API_KEY=... && python -m dictation`) requires zero config files. Dependencies are minimal and justified: `assemblyai` (STT SDK), `pyaudio` (mic capture), `evdev` (kernel input on Linux) — nothing gratuitous. Code formatting is enforced by **Ruff**, and the CI pipeline runs type checking, linting, and tests on every commit. The goal is a codebase where any single file can be read top-to-bottom and understood in isolation.

## Configuration

Murmur uses a layered configuration system:

```
Defaults (config.py dataclasses)
    ▼ overridden by
~/.config/dictation/config.json
    ▼ overridden by
Environment variables (ASSEMBLYAI_API_KEY, DICTATION_HOTKEY_MODE, etc.)
```

All configuration is expressed as nested dataclasses (`DictationConfig` → `HotkeyConfig`, `TranscriberConfig`, `InjectorConfig`, `FeedbackConfig`). This means the config is always valid at construction time, IDE autocompletion works, and serialization to/from JSON is trivial.

### Key Tuning Parameters

| Parameter | Default | Purpose |
|---|---|---|
| `hotkey.mode` | `push_to_talk` | `push_to_talk` (hold to record) or `toggle` (press to start/stop) |
| `hotkey.modifiers` | `[KEY_LEFTCTRL, KEY_LEFTSHIFT]` | Modifier keys for the hotkey combo |
| `hotkey.trigger` | `KEY_SPACE` | Trigger key |
| `transcriber.format_turns` | `true` | Get punctuated/cased output from AssemblyAI |
| `transcriber.end_of_turn_confidence_threshold` | `0.4` | How confident the model must be that you've stopped speaking |
| `transcriber.max_turn_silence` | `1280` ms | Maximum silence before forcing an end-of-turn |
| `injector.trailing_space` | `true` | Add a space after injected text |
| `injector.key_delay` | `0` ms | Delay between simulated keystrokes (increase if target app drops characters) |
| `feedback.audio_enabled` | `true` | Play start/stop beeps |

## System Requirements

### Linux (Wayland) — Primary Target

- Python ≥ 3.10
- `ydotool` installed, `ydotoold` daemon running
- User in the `input` group (for both evdev and ydotool)
- PortAudio system library (`portaudio19-dev` / `portaudio-devel`)
- Working microphone
- Internet connection (for AssemblyAI)

### macOS — Secondary Target

- Python ≥ 3.10
- Accessibility permissions granted to the Python process / Terminal
- Microphone permissions granted
- Internet connection (for AssemblyAI)

## Roadmap

### Phase 1 — Foundation (current)

- [x] Abstract base classes for all components
- [x] evdev hotkey listener (Wayland-native)
- [x] pynput hotkey listener (macOS/X11 fallback)
- [x] AssemblyAI Universal-Streaming v3 transcriber
- [x] ydotool text injector (Linux)
- [x] pynput text injector (macOS)
- [x] Audio feedback (start/stop beeps)
- [x] Layered configuration (dataclasses + env vars + JSON)
- [x] Push-to-talk and toggle modes
- [x] Main orchestrator wiring everything together

### Phase 2 — Reliability & Polish

- [ ] Pyright strict mode compliance across all modules
- [ ] pytest suite: unit tests with mocked backends, integration tests for real hardware paths
- [ ] Automatic reconnection on AssemblyAI WebSocket disconnect
- [ ] Graceful handling of ydotoold crash/restart mid-session
- [ ] Buffered injection mode: accumulate all text, inject on hotkey release (alternative to live injection)
- [ ] Session metrics logging (audio duration, latency, word count)

### Phase 3 — Local & Offline

- [ ] Whisper.cpp / faster-whisper transcriber backend (offline mode)
- [ ] Automatic fallback: try AssemblyAI → fall back to local Whisper on network failure
- [ ] VAD (voice activity detection) to skip silence before sending to local model

### Phase 4 — UX

- [ ] System tray icon with recording state indicator
- [ ] Desktop notification on errors (e.g. "ydotoold not running")
- [ ] Live transcript overlay (floating window showing words as they arrive)
- [ ] Per-application profiles (different hotkeys or behavior for different apps)
- [ ] Custom vocabulary / keyterms prompting via config

### Phase 5 — Packaging & Distribution

- [ ] Systemd user service file for auto-start
- [ ] `.deb` / `.rpm` / AUR packaging
- [ ] Homebrew formula (macOS)
- [ ] Flatpak (with appropriate `uinput` portal permissions)
- [ ] One-line install script

## Project Structure

```
murmur/
├── pyproject.toml
├── README.md
├── MURMUR_VISION.md          ← you are here
│
├── dictation/
│   ├── __init__.py
│   ├── __main__.py            # python -m dictation entry point
│   ├── main.py                # DictationApp orchestrator
│   ├── config.py              # Dataclass configuration
│   │
│   ├── hotkey/
│   │   ├── __init__.py        # Factory: create_hotkey_listener()
│   │   ├── base.py            # HotkeyListener ABC
│   │   ├── evdev_listener.py  # Linux/Wayland (reads /dev/input)
│   │   └── pynput_listener.py # macOS/X11
│   │
│   ├── transcriber/
│   │   ├── __init__.py        # Factory: create_transcriber()
│   │   ├── base.py            # Transcriber ABC
│   │   └── assemblyai_transcriber.py  # AssemblyAI Universal-Streaming v3
│   │
│   ├── injector/
│   │   ├── __init__.py        # Factory: create_injector()
│   │   ├── base.py            # TextInjector ABC
│   │   ├── ydotool_injector.py    # Linux (uinput)
│   │   └── pynput_injector.py     # macOS
│   │
│   └── feedback/
│       ├── __init__.py
│       └── audio_feedback.py  # PCM sine tones via PyAudio
│
└── tests/
    ├── test_config.py
    ├── test_hotkey.py
    ├── test_transcriber.py
    └── test_injector.py
```

## License

MIT
