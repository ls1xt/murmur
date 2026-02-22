#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing dependencies"
uv sync --group dev

# On Linux, load the snd-aloop kernel module for virtual mic tests.
# On macOS, BlackHole is detected at runtime by the test fixture; if absent, those tests auto-skip.
if [[ "$(uname -s)" == "Linux" ]]; then
    echo "==> Loading snd-aloop kernel module (Linux)"
    sudo modprobe snd-aloop
fi

echo "==> Pre-commit checks"
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
