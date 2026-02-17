---
phase: quick-fix-verification
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - uv.lock
  - murmur/transcriber/assemblyai.py
  - murmur/transcriber/base.py
  - murmur/main.py
  - murmur/feedback/audio.py
  - murmur/injector/ydotool.py
  - pyproject.toml
autonomous: true
requirements: []
must_haves:
  truths:
    - "`uv lock` completes without error and pystray/Pillow appear in uv.lock"
    - "_is_streaming reads/writes are protected by a threading.Lock in AssemblyAITranscriber"
    - "DictationApp._lock is either used to guard _on_activate/_on_deactivate or removed entirely"
    - "PyAudio stream and pa instance are always closed even if stream.write() raises"
    - "Audio streaming errors are always logged, whether or not _on_error callback is set"
    - "pgrep FileNotFoundError returns False and logs a warning instead of silently returning True"
    - "pyproject.toml has [project.scripts] entry mapping murmur to murmur.main:main"
    - "All 93 existing tests still pass after changes"
  artifacts:
    - path: "uv.lock"
      provides: "Locked dependency manifest with pystray and Pillow"
    - path: "murmur/transcriber/assemblyai.py"
      provides: "Thread-safe _is_streaming and logged errors"
    - path: "murmur/transcriber/base.py"
      provides: "Lock defined on base Transcriber"
    - path: "murmur/main.py"
      provides: "DictationApp with _lock used or removed"
    - path: "murmur/feedback/audio.py"
      provides: "PyAudio resources closed in try/finally"
    - path: "murmur/injector/ydotool.py"
      provides: "pgrep FileNotFoundError handled correctly"
    - path: "pyproject.toml"
      provides: "[project.scripts] CLI entry point"
  key_links:
    - from: "murmur/transcriber/base.py"
      to: "murmur/transcriber/assemblyai.py"
      via: "_streaming_lock defined in base, used in subclass"
      pattern: "_streaming_lock"
---

<objective>
Fix all seven verification issues found during the post-phase-3 audit.

Purpose: The project is feature-complete but has thread-safety gaps, a resource leak, silent error drops, an incorrect availability check, a stale lockfile, and a missing CLI entry point. Fixing these makes the daemon production-ready.
Output: Seven targeted fixes across six files, all existing tests still passing.
</objective>

<execution_context>
@/home/leon/.claude/get-shit-done/workflows/execute-plan.md
@/home/leon/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Regenerate uv.lock and add CLI entry point</name>
  <files>uv.lock, pyproject.toml</files>
  <action>
    Two changes in one commit since they both touch project configuration:

    1. In `pyproject.toml`, add a `[project.scripts]` section after `[project]`:
       ```toml
       [project.scripts]
       murmur = "murmur.main:main"
       ```
       This lets `pip install .` / `uv tool install .` create a `murmur` CLI command that calls `main()`.

    2. Regenerate the lockfile so pystray and Pillow (already in `[project].dependencies`) are reflected:
       ```bash
       uv lock
       ```
       Do not manually edit `uv.lock`. Just run the command and commit the result.
  </action>
  <verify>
    ```bash
    grep -c "name = \"pystray\"" uv.lock
    grep -c "name = \"pillow\"" uv.lock
    grep "murmur = " pyproject.toml
    uv lock --check
    ```
    All four commands should succeed (grep exits 0 if found, uv lock --check exits 0 if lockfile is consistent).
  </verify>
  <done>
    `uv.lock` contains pystray and pillow entries, `uv lock --check` exits 0, and `pyproject.toml` contains `murmur = "murmur.main:main"` under `[project.scripts]`.
  </done>
</task>

<task type="auto">
  <name>Task 2: Protect _is_streaming with a threading.Lock and log unhandled errors</name>
  <files>murmur/transcriber/base.py, murmur/transcriber/assemblyai.py</files>
  <action>
    Fix two issues in the transcriber stack:

    **A. Add `_streaming_lock` to base class (`murmur/transcriber/base.py`)**

    In `Transcriber.__init__`, add:
    ```python
    import threading
    self._streaming_lock = threading.Lock()
    ```
    Change `_is_streaming` from a plain `bool` to a property backed by `_streaming_lock`:
    - Add `_streaming: bool = False` as the private backing field.
    - Replace `self._is_streaming = False` with `self._streaming = False`.
    - Add a property:
      ```python
      @property
      def _is_streaming(self) -> bool:
          with self._streaming_lock:
              return self._streaming

      @_is_streaming.setter
      def _is_streaming(self, value: bool) -> None:
          with self._streaming_lock:
              self._streaming = value
      ```
    This keeps the `_is_streaming` attribute name used throughout `assemblyai.py` unchanged -- no changes needed there for the thread-safety fix itself.

    **B. Log errors even when `_on_error` is None (`murmur/transcriber/assemblyai.py`)**

    In `_stream_audio`, change lines 93-95 from:
    ```python
    except Exception as e:
        if self._is_streaming and self._on_error is not None:
            self._on_error(e)
    ```
    to:
    ```python
    except Exception as e:
        if self._is_streaming:
            logger.error("Audio stream error: %s", e)
            if self._on_error is not None:
                self._on_error(e)
    ```
    This ensures errors are always logged regardless of whether a callback is registered.
  </action>
  <verify>
    ```bash
    cd /home/leon/murmur && python -c "
    from murmur.transcriber.base import Transcriber
    import threading

    class T(Transcriber):
        def start(self): pass
        def stop(self): pass

    t = T()
    assert hasattr(t, '_streaming_lock'), 'no lock'
    assert isinstance(t._streaming_lock, threading.Lock), 'wrong type'
    t._is_streaming = True
    assert t._is_streaming is True
    t._is_streaming = False
    assert t._is_streaming is False
    print('OK')
    "
    python -m pytest tests/ -q 2>&1 | tail -5
    ```
  </verify>
  <done>
    `_streaming_lock` exists on Transcriber, reads/writes of `_is_streaming` go through the lock, all 93 tests pass.
  </done>
</task>

<task type="auto">
  <name>Task 3: Fix DictationApp._lock, PyAudio resource leak, and pgrep FileNotFoundError</name>
  <files>murmur/main.py, murmur/feedback/audio.py, murmur/injector/ydotool.py</files>
  <action>
    Three targeted fixes:

    **A. Use or remove `_lock` in DictationApp (`murmur/main.py`)**

    The `_lock` at line 44 is unused. Use it to guard against concurrent `_on_activate`/`_on_deactivate` calls (e.g., rapid double-press):

    Change `_on_activate`:
    ```python
    def _on_activate(self) -> None:
        """Called when the hotkey is activated (start recording)."""
        with self._lock:
            if self.transcriber.is_streaming:
                return  # already recording
        logger.info("Recording started")
        self.feedback.play_start()
        self.notifier.info("Recording started")
        self.tray.set_state("recording")
        threading.Thread(target=self.transcriber.start, daemon=True).start()
    ```

    Change `_on_deactivate`:
    ```python
    def _on_deactivate(self) -> None:
        """Called when the hotkey is deactivated (stop recording)."""
        with self._lock:
            if not self.transcriber.is_streaming:
                return  # already stopped
        logger.info("Recording stopped")
        self.feedback.play_stop()
        self.notifier.info("Recording stopped")
        self.tray.set_state("idle")
        threading.Thread(target=self.transcriber.stop, daemon=True).start()
    ```

    **B. Fix PyAudio resource leak in `_play_tone` (`murmur/feedback/audio.py`)**

    Wrap the PyAudio open/write/close block in `try/finally` so `stream` and `pa` are always cleaned up. Replace the `try` block at lines 69-82:
    ```python
    pa: Any = _pyaudio.PyAudio()
    try:
        stream: Any = pa.open(
            format=_pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            output=True,
        )
        try:
            stream.write(samples)
        finally:
            stream.stop_stream()
            stream.close()
    finally:
        pa.terminate()
    ```
    Keep the outer `except Exception` that logs the error -- wrap around the whole `pa = ...` block.

    **C. Fix pgrep FileNotFoundError in `is_available` (`murmur/injector/ydotool.py`)**

    In `is_available`, the `except (subprocess.TimeoutExpired, FileNotFoundError): pass` at line 61 silently ignores a missing `pgrep` and falls through to `return True`. Fix it:
    ```python
    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        logger.warning("pgrep not found; cannot verify ydotoold is running")
        return False
    ```
  </action>
  <verify>
    ```bash
    cd /home/leon/murmur && python -m pytest tests/ -q 2>&1 | tail -5
    python -c "
    import ast, sys
    for path in ['murmur/main.py', 'murmur/feedback/audio.py', 'murmur/injector/ydotool.py']:
        ast.parse(open(path).read())
    print('All files parse OK')
    "
    grep -n "_lock" murmur/main.py
    grep -n "finally" murmur/feedback/audio.py
    grep -n "FileNotFoundError" murmur/injector/ydotool.py
    ```
  </verify>
  <done>
    `_lock` guards activate/deactivate in `main.py`, `audio.py` uses nested try/finally for stream and pa cleanup, `ydotool.py` returns `False` with a warning on `FileNotFoundError`, all 93 tests pass.
  </done>
</task>

</tasks>

<verification>
After all three tasks:

```bash
cd /home/leon/murmur
python -m pytest tests/ -q
uv lock --check
grep "project.scripts" pyproject.toml -A2
python -c "from murmur.main import main; print('entry point importable')"
```

All 93 tests pass, lockfile is consistent, entry point is declared and importable.
</verification>

<success_criteria>
- `uv lock --check` exits 0 (pystray and Pillow in lockfile)
- `pyproject.toml` declares `murmur = "murmur.main:main"` under `[project.scripts]`
- `Transcriber._streaming_lock` protects all reads/writes of `_is_streaming`
- Audio stream errors are always logged in `assemblyai.py` even when `_on_error` is None
- `DictationApp._lock` is used in `_on_activate`/`_on_deactivate`
- PyAudio `stream` and `pa` are closed in `try/finally` blocks in `audio.py`
- `pgrep` FileNotFoundError returns `False` + warning in `ydotool.py`
- `pytest` reports 93 passed, 0 failed
</success_criteria>

<output>
After completion, create `.planning/quick/1-fix-all-verification-issues/1-SUMMARY.md` using the summary template.
</output>
