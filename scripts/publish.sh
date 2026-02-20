#!/usr/bin/env bash
# Publish murmur-dictation to PyPI.
# Usage:
#   ./scripts/publish.sh           # dry-run (build only, no upload)
#   ./scripts/publish.sh --publish # build + upload to PyPI
#
# Requires: uv (for build), uv publish or twine (for upload)
# Set PYPI_TOKEN env var before running: export PYPI_TOKEN=pypi-...
#
# Note: Package is named "murmur-dictation" on PyPI because "murmur" is taken.
# Install with: pip install murmur-dictation
#
set -euo pipefail

DRY_RUN=true
for arg in "$@"; do
    [[ "$arg" == "--publish" ]] && DRY_RUN=false
done

echo "==> Cleaning dist/"
rm -rf dist/

echo "==> Building wheel and sdist"
uv build

echo "==> Wheel contents:"
python3 -m zipfile -l dist/*.whl | head -30

if $DRY_RUN; then
    echo ""
    echo "Dry run complete. Built artifacts:"
    ls -lh dist/
    echo ""
    echo "To publish, run: PYPI_TOKEN=pypi-... ./scripts/publish.sh --publish"
    exit 0
fi

if [[ -z "${PYPI_TOKEN:-}" ]]; then
    echo "Error: PYPI_TOKEN environment variable not set."
    echo "Get a token at: https://pypi.org/manage/account/token/"
    exit 1
fi

echo "==> Uploading to PyPI"
uv publish --token "$PYPI_TOKEN"

echo "==> Published successfully!"
echo "Install with: pip install murmur-dictation"
