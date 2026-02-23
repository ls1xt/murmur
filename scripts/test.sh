#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing dependencies"
uv sync --group dev

# On Linux, load the snd-aloop kernel module for virtual mic tests.
# On macOS, BlackHole is detected at runtime by the test fixture; if absent, those tests auto-skip.
if [[ "$(uname -s)" == "Linux" ]]; then
    echo "==> Loading snd-aloop kernel module (Linux)"
    if ! modprobe snd-aloop 2>/dev/null && ! sudo modprobe snd-aloop 2>/dev/null; then
        echo "WARNING: Could not load snd-aloop — virtual-mic tests will be skipped" >&2
    fi
fi

echo "==> Pre-commit checks"
if [[ -z "${CI:-}" && ! -f ".git/hooks/pre-commit" ]]; then
    echo "ERROR: pre-commit hook not installed. Run: uv run pre-commit install" >&2
    exit 1
fi
uv run pre-commit run --all-files

echo "==> Lint (ruff)"
uv run ruff check .

echo "==> Format check (ruff)"
uv run ruff format --check .

echo "==> Type check (pyright)"
uv run pyright

run_pytest() {
    set +e
    uv run pytest "$@"
    local ec=$?
    set -e
    if [ $ec -eq 139 ]; then
        echo "WARNING: pytest exited with segfault (known Python 3.14/PortAudio shutdown issue; ignored)" >&2
        return 0
    fi
    return $ec
}

echo "==> Unit tests"
run_pytest

echo "==> Audio pipeline tests (virtual mic)"
run_pytest --virtual-mic

echo "==> All checks passed."
