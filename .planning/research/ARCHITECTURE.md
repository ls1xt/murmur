# Architecture Research

**Domain:** System daemon with pluggable backends — Python voice dictation tool
**Researched:** 2026-02-17
**Confidence:** HIGH (based on official Python docs, existing codebase analysis, verified patterns)

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         DictationApp                             │
│                     (dictation/main.py)                          │
│                     Orchestrator layer                            │
│                                                                  │
│  ┌──────────────┐   callbacks   ┌──────────────────────────────┐ │
│  │   Hotkey     │──────────────▶│      Transcriber              │ │
│  │   Listener   │               │    (ABC + factory)            │ │
│  │(ABC+factory) │               └────────────┬─────────────────┘ │
│  └──────────────┘                            │ on_final callback  │
│         │                                    ▼                   │
│   on_activate /                    ┌──────────────────────────┐  │
│   on_deactivate                    │     Text Injector         │  │
│                                    │    (ABC + factory)        │  │
│  ┌──────────────┐                  └──────────────────────────┘  │
│  │   Feedback   │                                                 │
│  │ (AudioFeed-  │◀── beep on activate/deactivate                 │
│  │    back)     │                                                 │
│  └──────────────┘                                                 │
├──────────────────────────────────────────────────────────────────┤
│                       Backend Layer                               │
│                                                                   │
│  Hotkey:       EvdevHotkeyListener │ PynputHotkeyListener        │
│  Transcriber:  AssemblyAITranscriber │ (future: WhisperTranscriber)│
│  Injector:     YdotoolInjector │ PynputInjector                  │
└──────────────────────────────────────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `DictationApp` | Orchestrates pipeline, lifecycle, signal handling | All components via callbacks |
| `HotkeyListener` ABC | Detect hotkey press/release, call on_activate / on_deactivate | DictationApp (via callbacks) |
| `Transcriber` ABC | Manage mic stream + STT backend, emit transcript events | DictationApp (via callbacks), audio hardware |
| `TextInjector` ABC | Inject text into focused window via input simulation | OS input subsystem (subprocess or uinput) |
| `AudioFeedback` | Play start/stop tones | Audio hardware (PyAudio/PortAudio) |
| `DictationConfig` | Nested dataclasses, env var overrides, JSON file | All components (injected at construction) |
| Factory functions | Inspect config, instantiate correct concrete backend | Config dataclass → ABC instance |

## Recommended Project Structure

```
murmur/
├── pyproject.toml            # project metadata, dependencies, tool config
├── README.md
├── VISION.md
│
├── dictation/                # importable package (flat layout — not src/)
│   ├── __init__.py           # public API surface
│   ├── __main__.py           # python -m dictation entry point
│   ├── main.py               # DictationApp orchestrator
│   ├── config.py             # DictationConfig + sub-configs (dataclasses)
│   │
│   ├── hotkey/
│   │   ├── __init__.py       # exports create_hotkey_listener() factory
│   │   ├── base.py           # HotkeyListener ABC + shared logic
│   │   ├── evdev_listener.py # Linux/Wayland — reads /dev/input/event*
│   │   └── pynput_listener.py# macOS/X11 fallback
│   │
│   ├── transcriber/
│   │   ├── __init__.py       # exports create_transcriber() factory
│   │   ├── base.py           # Transcriber ABC + callback protocol
│   │   └── assemblyai.py     # AssemblyAI Universal-Streaming v3
│   │
│   ├── injector/
│   │   ├── __init__.py       # exports create_injector() factory
│   │   ├── base.py           # TextInjector ABC
│   │   ├── ydotool.py        # Linux uinput via ydotool subprocess
│   │   └── pynput.py         # macOS via pynput keyboard.Controller
│   │
│   └── feedback/
│       ├── __init__.py
│       └── audio.py          # AudioFeedback — PCM sine tones via PyAudio
│
└── tests/
    ├── conftest.py            # shared fixtures, mock factories
    ├── test_config.py
    ├── hotkey/
    │   ├── test_base.py       # ABC contract tests
    │   └── test_evdev.py      # evdev-specific logic with mocked devices
    ├── transcriber/
    │   ├── test_base.py
    │   └── test_assemblyai.py # mocked StreamingClient
    └── injector/
        ├── test_base.py
        └── test_ydotool.py    # mocked subprocess
```

### Structure Rationale

- **Flat layout (not `src/`):** This is a local daemon, not a distributed library. Flat layout is simpler, avoids the mandatory editable install step during development, and is appropriate for tools where you control the install environment. The official Python packaging guide confirms both layouts are valid; flat layout is preferred for applications (as opposed to libraries meant for PyPI distribution).
- **Subpackages by concern:** `hotkey/`, `transcriber/`, `injector/`, `feedback/` match the pipeline stages. Each subpackage owns its ABC, factory, and all concrete backends for that stage. Adding a new backend = adding one file in the right subpackage, no other changes.
- **Factory in `__init__.py`:** `create_hotkey_listener(config) -> HotkeyListener` lives in the subpackage's `__init__.py`. Callers import from `dictation.hotkey`, not from concrete backend modules. This is the standard plugin factory pattern — consumers never import implementation classes directly.
- **Tests mirror source:** `tests/hotkey/`, `tests/transcriber/`, etc. mirror the package structure. This scales cleanly and makes it obvious which test file covers which module.

## Architectural Patterns

### Pattern 1: ABC + Factory Pattern for Pluggable Backends

**What:** Define behavior contract with ABC, instantiate correct backend in factory function based on config, never expose concrete classes to the orchestrator.

**When to use:** Any time you have multiple backends for the same abstraction and may add more. Always use ABC over `Protocol` for this case — ABCs enforce the contract at class definition time and provide a natural place to put shared implementation (like the callback registration logic).

**Trade-offs:** ABCs require explicit subclassing (nominal typing). `Protocol` uses structural typing (duck typing) and is easier for third-party extensions but doesn't enforce the contract at class instantiation. For an internal codebase with a known set of backends, ABC is strictly better — failures surface at class definition, not at call sites.

**Example:**
```python
# dictation/hotkey/base.py
from abc import ABC, abstractmethod
from typing import Callable

class HotkeyListener(ABC):
    def __init__(self, mode: str = "push_to_talk") -> None:
        self.mode = mode
        self._on_activate: Callable[[], None] | None = None
        self._on_deactivate: Callable[[], None] | None = None

    def set_callbacks(
        self,
        on_activate: Callable[[], None],
        on_deactivate: Callable[[], None],
    ) -> None:
        self._on_activate = on_activate
        self._on_deactivate = on_deactivate

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    # Shared logic lives in base — concrete classes call these
    def _handle_hotkey_press(self) -> None:
        if self.mode == "push_to_talk" and self._on_activate:
            self._on_activate()
        elif self.mode == "toggle":
            ...  # toggle logic

# dictation/hotkey/__init__.py
from dictation.config import HotkeyConfig
from dictation.hotkey.base import HotkeyListener

def create_hotkey_listener(config: HotkeyConfig) -> HotkeyListener:
    backend = config.backend
    if backend == "auto":
        backend = _detect_backend()
    if backend == "evdev":
        from dictation.hotkey.evdev_listener import EvdevHotkeyListener
        return EvdevHotkeyListener(...)
    elif backend == "pynput":
        from dictation.hotkey.pynput_listener import PynputHotkeyListener
        return PynputHotkeyListener(...)
    raise ValueError(f"Unknown hotkey backend: {backend}")
```

### Pattern 2: Threading over asyncio for Audio + WebSocket Pipeline

**What:** Use `threading.Thread` for all concurrent operations — hotkey listener loop, mic capture, and the AssemblyAI SDK's internal WebSocket. Coordinate with `threading.Event` for lifecycle control.

**When to use:** When mixing blocking C-extension code (PyAudio/PortAudio, evdev device reads) with Python concurrency. Threading is correct here; asyncio is not.

**Why threading beats asyncio for this domain (HIGH confidence):**
- PyAudio/PortAudio audio I/O is a blocking C extension. It cannot be used with asyncio without running it in a thread executor — which means you get threading complexity plus asyncio overhead.
- evdev uses `selectors.DefaultSelector` for multiplexing device file descriptors. This is also blocking I/O best handled in a dedicated thread.
- The AssemblyAI SDK is thread-based internally. It manages its own WebSocket thread. Introducing asyncio creates an impedance mismatch requiring `asyncio.run_coroutine_threadsafe()` bridges — complexity for no benefit.
- Python's GIL is released during C-extension I/O (PortAudio, socket reads). Threading gives true parallelism for audio + network in this case.
- asyncio shines for managing thousands of concurrent connections in a server. For a single-user daemon with 3-4 threads, threading is simpler, more readable, and equally performant.

**Trade-offs:** Threading requires explicit synchronization (threading.Event for shutdown, threading.Lock for shared state). These are well-understood patterns. The cost is manageable for this scale.

**Example:**
```python
# Shutdown coordination pattern
class DictationApp:
    def __init__(self) -> None:
        self._stop_event = threading.Event()

    def run(self) -> None:
        signal.signal(signal.SIGINT, lambda s, f: self._stop_event.set())
        signal.signal(signal.SIGTERM, lambda s, f: self._stop_event.set())
        self.hotkey.start()          # starts background thread internally
        self._stop_event.wait()      # main thread blocks here
        self.shutdown()

    def shutdown(self) -> None:
        self.transcriber.stop()      # signals internal threads
        self.hotkey.stop()           # joins internal threads
```

### Pattern 3: Testability via Dependency Injection + Boundary Mocking

**What:** Test components at the boundary of hardware. Never test that `subprocess.run` was called with specific bytes — test that `TextInjector.inject("hello")` produces the correct subprocess invocation via mocked subprocess. For evdev, mock `evdev.InputDevice`, not the kernel.

**When to use:** Whenever a component calls hardware, the OS, or external services.

**Three test tiers:**

1. **Unit tests (mock at hardware boundary):** Mock `evdev.InputDevice`, `assemblyai.streaming.v3.StreamingClient`, `subprocess.run`. These are fast, run without hardware, cover all logic branches.

2. **Integration tests (marked, skipped on CI without hardware):** Use `pytest.mark.hardware` to gate tests that require real evdev devices, PortAudio, or ydotoold. Run on the developer machine; skip in CI by default.

3. **Contract tests (ABC compliance):** Parameterize against all concrete backends to verify they satisfy the ABC contract. This catches backends that override but don't call `super()`, or miss an edge case.

**Example:**
```python
# tests/injector/test_ydotool.py
from unittest.mock import MagicMock, patch
import pytest
from dictation.injector.ydotool import YdotoolInjector

def test_inject_calls_ydotool_with_correct_args():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        injector = YdotoolInjector(trailing_space=False)
        injector._resolved_path = "/usr/bin/ydotool"  # bypass shutil.which
        injector.inject("hello world")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "hello world" in cmd

# tests/hotkey/test_evdev.py
def test_hotkey_fires_on_modifier_plus_trigger(mock_evdev_device):
    listener = EvdevHotkeyListener(["KEY_LEFTCTRL"], "KEY_SPACE")
    activated = []
    listener.set_callbacks(on_activate=lambda: activated.append(1), on_deactivate=lambda: None)
    # Simulate key events through the mock device
    listener._handle_key_event(make_key_event(ecodes.KEY_LEFTCTRL, keystate=1))
    listener._handle_key_event(make_key_event(ecodes.KEY_SPACE, keystate=1))
    assert len(activated) == 1

# conftest.py — shared fixture
@pytest.fixture
def mock_evdev_device():
    with patch("evdev.InputDevice") as mock:
        mock.return_value.capabilities.return_value = {
            ecodes.EV_KEY: [ecodes.KEY_A, ecodes.KEY_Z, ecodes.KEY_SPACE]
        }
        yield mock
```

## Data Flow

### Push-to-Talk Flow

```
[User holds Ctrl+Shift+Space]
        │
        ▼
EvdevHotkeyListener._listen_loop()      ← background thread, selector-based
  reads EV_KEY events from /dev/input
        │
        ▼
HotkeyListener._handle_hotkey_press()   ← base class shared logic
        │
        ▼
DictationApp._on_activate()             ← callback, runs in hotkey thread
  AudioFeedback.play_start()            ← fire-and-forget beep
  threading.Thread(target=transcriber.start).start()
        │
        ▼
AssemblyAITranscriber.start()           ← background thread
  StreamingClient.connect()             ← SDK manages its own WebSocket thread
  MicrophoneStream → client.stream()    ← blocks on PortAudio C extension
        │
        ▼
AssemblyAI TurnEvents arrive
  on_partial(text) → DictationApp._on_partial_transcript()  ← log/preview
  on_final(text)   → DictationApp._on_final_transcript()
        │
        ▼
DictationApp._on_final_transcript(text)
        │
        ▼
YdotoolInjector.inject(text)
  subprocess.run(["ydotool", "type", "--clearmodifiers", "--", text])
        │
        ▼
[Text appears at cursor in focused application]

[User releases Ctrl+Shift+Space]
        │
        ▼
HotkeyListener._handle_hotkey_release()
        │
        ▼
DictationApp._on_deactivate()
  AudioFeedback.play_stop()
  threading.Thread(target=transcriber.stop).start()
        │
        ▼
AssemblyAITranscriber.stop()
  mic_stream.close()        ← unblocks client.stream()
  client.disconnect()       ← sends WebSocket terminate
  stream_thread.join()      ← waits for clean exit
```

### Configuration Flow

```
Defaults (dataclass field defaults)
    ▼ overridden by
~/.config/dictation/config.json
    ▼ overridden by
Environment variables (ASSEMBLYAI_API_KEY, DICTATION_HOTKEY_MODE, etc.)
    ▼
DictationConfig instance injected into factory functions
    ▼
Factory selects backend, passes sub-config to concrete class constructor
```

### Key Data Flows

1. **Audio path:** Microphone → PyAudio/PortAudio (C extension, blocking) → AssemblyAI SDK internal buffer → WebSocket → AssemblyAI cloud → TurnEvent callbacks → DictationApp → YdotoolInjector → subprocess → kernel uinput → focused window
2. **Hotkey path:** `/dev/input/event*` → evdev (blocking, selector-based) → key state tracking → callback → DictationApp
3. **Config path:** JSON + env vars → `DictationConfig.load()` → sub-config dataclasses → factory functions → concrete backends

## Scaling Considerations

This is a single-user desktop daemon. "Scaling" means robustness to edge cases, not horizontal scaling.

| Concern | Current | Improved (Phase 2) |
|---------|---------|---------------------|
| WebSocket disconnect | Hard failure | Auto-reconnect with exponential backoff |
| ydotoold crash mid-session | subprocess error logged | Detect and surface error notification |
| Rapid hotkey presses | Race between stop/start threads | Add `_lock` to serialise lifecycle transitions |
| Device disconnect (evdev) | Device removed from selector, warning logged | Already handled in existing code |
| Long dictation sessions | Memory: transcript list grows unbounded | Cap `_all_text_this_session` or flush periodically |

## Anti-Patterns

### Anti-Pattern 1: Importing Concrete Backends Directly

**What people do:** `from dictation.hotkey.evdev_listener import EvdevHotkeyListener` in orchestrator or tests.

**Why it's wrong:** Breaks the pluggability promise. If you add a Wayland-native backend later, you have to find all the call sites. Tests coupled to concrete classes don't test the contract; they test the implementation.

**Do this instead:** Always import from the subpackage, never from the module: `from dictation.hotkey import create_hotkey_listener`. Tests that need a specific backend import it explicitly and mark it as `@pytest.mark.hardware`.

### Anti-Pattern 2: asyncio for PyAudio + evdev

**What people do:** Wrap PyAudio and evdev in asyncio, use `loop.run_in_executor()` to bridge blocking I/O.

**Why it's wrong:** You get all the complexity of asyncio (event loop management, coroutine propagation, run_coroutine_threadsafe bridges) with none of the benefit. PyAudio and evdev are blocking C extensions that can't yield control to an event loop. The AssemblyAI SDK is thread-based. You end up with hidden threads inside executors anyway.

**Do this instead:** Use threading directly. Three or four daemon threads with threading.Event for shutdown is readable, debuggable, and idiomatic for this type of system daemon.

### Anti-Pattern 3: Testing Through the Orchestrator

**What people do:** Write all tests against `DictationApp`, providing it with mock backends, and assert on side effects.

**Why it's wrong:** `DictationApp` is the integration layer. Testing through it tests everything at once: if a test fails, it's unclear which component is broken. It also means tests can't verify ABC contract compliance in isolation.

**Do this instead:** Unit-test each component class in isolation using mocked dependencies. Write one or two integration tests for the full `DictationApp` pipeline with all mocks. This gives clear failure signals.

### Anti-Pattern 4: Flat Module Names for Backend Modules

**What people do:** Name backend files with the backend name as a prefix: `evdev_listener.py`, `assemblyai_transcriber.py` (the current flat layout).

**Why it's wrong:** Once inside the `hotkey/` subpackage, `evdev_listener.py` is redundant. The package already says "hotkey"; the module should say what the backend does, not repeat the parent context. Also, this naming convention doesn't generalize cleanly (e.g., `assemblyai_transcriber.py` becomes `transcriber/assemblyai_transcriber.py` — redundant).

**Do this instead:** Inside the subpackage, use bare backend names: `hotkey/evdev.py`, `hotkey/pynput.py`, `transcriber/assemblyai.py`, `injector/ydotool.py`, `injector/pynput.py`. Shorter, cleaner, and the subpackage provides context.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| AssemblyAI Universal-Streaming v3 | SDK-managed WebSocket (`StreamingClient`), event callbacks | SDK handles WebSocket threading internally; all callbacks fire on SDK's thread, not main thread |
| ydotoold daemon | `subprocess.run()` per injection | Stateless; each `inject()` spawns a new ydotool process. ydotoold stays alive independently |
| PortAudio (via PyAudio) | `aai.extras.MicrophoneStream` wrapping `pyaudio.PyAudio().open()` | Blocking C extension; must run in dedicated thread |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `HotkeyListener` → `DictationApp` | Callbacks (`on_activate`, `on_deactivate`) registered at startup | Callbacks fire from the hotkey listener's background thread — `DictationApp` must be thread-safe |
| `Transcriber` → `DictationApp` | Callbacks (`on_partial`, `on_final`, `on_error`) registered at startup | Callbacks fire from AssemblyAI SDK's internal thread |
| `DictationApp` → `TextInjector` | Direct method call (`injector.inject(text)`) | Called from `on_final` callback, which runs in SDK thread — injection is synchronous |
| `DictationApp` → `AudioFeedback` | Direct method call (`feedback.play_start()`) | Beep plays in main/callback thread; must be non-blocking or fire its own thread |
| Factory functions → Config | Config dataclasses passed by value to constructors | No shared mutable config state after construction |

## Build Order for Restructuring

The dependency graph determines build order. Later components can't be compiled/tested until their dependencies exist.

```
Phase 1: Foundation
    pyproject.toml + package skeleton (dictation/__init__.py etc.)
        │
        ▼
    config.py (DictationConfig + sub-configs)
        │
        ▼
    hotkey/base.py  ←──┐
    transcriber/base.py │  ABCs first — everything depends on them
    injector/base.py  ──┘
        │
        ▼
Phase 2: Concrete Backends (can be parallelized)
    hotkey/evdev.py
    hotkey/pynput.py
    transcriber/assemblyai.py
    injector/ydotool.py
    injector/pynput.py
    feedback/audio.py
        │
        ▼
Phase 3: Factories + Wiring
    hotkey/__init__.py (create_hotkey_listener)
    transcriber/__init__.py (create_transcriber)
    injector/__init__.py (create_injector)
        │
        ▼
Phase 4: Orchestrator + Entry Points
    main.py (DictationApp)
    __main__.py (python -m dictation)
        │
        ▼
Phase 5: Tests
    tests/ (mirrors package structure)
    Pyright strict mode compliance
```

**Key dependency rule:** ABCs must exist before any concrete backend. Factories must exist before the orchestrator. Tests can be written against the ABCs before concrete backends exist (using mock implementations), which enables TDD.

## Sources

- [Python Packaging: src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) — HIGH confidence, official Python packaging authority
- [Python abc module documentation](https://docs.python.org/3/library/abc.html) — HIGH confidence, official CPython docs
- [PEP 544: Protocols — Structural Subtyping](https://peps.python.org/pep-0544/) — HIGH confidence, official PEP
- [Python threading module documentation](https://docs.python.org/3/library/threading.html) — HIGH confidence, official CPython docs
- [Super Fast Python: asyncio vs threading](https://superfastpython.com/asyncio-vs-threading/) — MEDIUM confidence, multiple sources agree
- [pytest-subprocess](https://pypi.org/project/pytest-subprocess/) — MEDIUM confidence, widely used, official PyPI listing
- [Existing codebase analysis](file:///home/leon/murmur/) — HIGH confidence, direct inspection of working code
- [VISION.md](file:///home/leon/murmur/VISION.md) — HIGH confidence, project's own design document

---
*Architecture research for: Murmur — Python system daemon with pluggable backends*
*Researched: 2026-02-17*
