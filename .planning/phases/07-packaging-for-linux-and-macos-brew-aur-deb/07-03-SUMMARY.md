---
plan: "07-03"
phase: "07"
status: complete
completed: 2026-02-20
---

# Plan 07-03: PyPI Packaging

## What was built

Prepared murmur for PyPI distribution with complete metadata and a publish workflow.

### Key decisions

- **Package renamed to `murmur-dictation`**: The name "murmur" is already taken on PyPI (v0.1.3 exists). The installed command remains `murmur` for UX consistency — only the PyPI package name changed.
- Added `authors`, `keywords`, `classifiers`, and `[project.urls]` to pyproject.toml
- Added `[tool.hatch.build.targets.wheel]` (packages = ["murmur"]) and `[tool.hatch.build.targets.sdist]` (excludes .planning, tests, scripts, packaging)

### Publish workflow

`scripts/publish.sh` provides:
- Dry-run mode (default): builds wheel + sdist, shows contents
- `--publish` mode: uploads to PyPI using `uv publish --token $PYPI_TOKEN`

## Files modified/created

- `pyproject.toml` — renamed to murmur-dictation, added full PyPI metadata, hatch build targets
- `scripts/publish.sh` — repeatable build + publish script with dry-run guard
- `.gitignore` — added `.pypirc`

## Self-Check: PASSED

- `uv build` succeeded: dist/murmur_dictation-0.1.0-py3-none-any.whl, dist/murmur_dictation-0.1.0.tar.gz ✓
- Wheel contains only murmur/ Python source — no .sh/.service/.plist files ✓
- `bash -n scripts/publish.sh` — syntax OK ✓
- `grep "classifiers" pyproject.toml` — present ✓
- `grep "dist/" .gitignore` — dist/ already excluded ✓

## key-files

### created
- scripts/publish.sh

### modified
- pyproject.toml
- .gitignore
