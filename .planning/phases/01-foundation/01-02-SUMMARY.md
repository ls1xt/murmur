# Plan 01-02 Summary: Pyright Strict + Ruff Compliance

**Completed:** 2026-02-17
**Duration:** ~20 minutes

## What Was Done

Achieved zero errors from Pyright strict mode and zero violations from Ruff across all `murmur/` modules.

## Key Fixes

### Pyright Strict (151 errors -> 0)

1. **Untyped third-party libraries (evdev, assemblyai, pyaudio):**
   - Created typed wrapper functions and module-level constants with explicit `int`, `str`, `dict` annotations
   - Used `Any` for SDK objects with targeted `# type: ignore[reportUnknownMemberType]` comments
   - Used `importlib.import_module()` for `assemblyai.streaming.v3` (attribute access fails at runtime)

2. **Config `_from_dict` method:**
   - Extracted `_apply_section()` helper to isolate `Any` boundary from JSON deserialization
   - Used explicit `Any` casts to bypass strict-mode tracking of untyped JSON values

3. **PyAudio conditional import:**
   - Refactored from try/except with constant redefinition to `_load_pyaudio()` function
   - Module-level `_pyaudio: Any = None` avoids `reportConstantRedefinition`

4. **Signal handler typing:**
   - Annotated as `signum: int, frame: types.FrameType | None`

### Ruff (5 violations -> 0)

- SIM102: Combined nested `if` statements using `and`
- SIM105: Replaced `try/except/pass` with `contextlib.suppress()`
- SIM114: Combined duplicate `if` branches with `or`

### Pyright Config

```toml
[tool.pyright]
typeCheckingMode = "strict"
pythonVersion = "3.10"
venvPath = "."
venv = ".venv"
reportMissingModuleSource = "none"
reportMissingTypeStubs = "none"
reportPrivateUsage = "none"
reportUntypedFunctionDecorator = "none"
```

## Verification

- `pyright murmur/` -- 0 errors
- `ruff check murmur/` -- 0 violations
- `ruff format --check murmur/` -- all files already formatted
- No bare `# type: ignore` comments (all have specific codes)
- No `from typing import Optional` imports
