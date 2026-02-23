#!/usr/bin/env bash
# publish-tap.sh — Tag a murmur release and publish the Homebrew tap formula.
#
# Usage:
#   ./scripts/publish-tap.sh [--version v0.1.0] [--tap-dir PATH]
#
# What it does:
#   1. Reads the version from pyproject.toml (or --version flag)
#   2. Creates and pushes a git tag (vX.Y.Z) to origin
#   3. Downloads the GitHub release archive and computes its SHA256
#   4. Writes the SHA256 into packaging/homebrew/tap/Formula/murmur.rb
#   5. Commits + pushes the updated formula to the homebrew-murmur tap repo
#
# Prerequisites:
#   - git push access to git@github.com:ls1xt/murmur.git
#   - A local clone (or the tap-dir) of git@github.com:ls1xt/homebrew-murmur.git
#     at $TAP_DIR (default: ../homebrew-murmur relative to this repo)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMULA_SRC="$REPO_ROOT/packaging/homebrew/tap/Formula/murmur.rb"

# ---------- defaults ----------
GITHUB_USER="ls1xt"
GITHUB_REPO="murmur"
TAP_DIR="${TAP_DIR:-$REPO_ROOT/../homebrew-murmur}"

# ---------- parse args ----------
VERSION=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --version) VERSION="$2"; shift 2 ;;
    --tap-dir) TAP_DIR="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

# ---------- read version from pyproject.toml ----------
if [[ -z "$VERSION" ]]; then
  VERSION="v$(python3 -c "import tomllib; print(tomllib.load(open('$REPO_ROOT/pyproject.toml','rb'))['project']['version'])")"
fi
TAG="$VERSION"
echo "==> Publishing murmur $TAG"

# ---------- create + push git tag ----------
cd "$REPO_ROOT"
if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "  Tag $TAG already exists locally."
else
  echo "  Creating git tag $TAG ..."
  git tag -a "$TAG" -m "Release $TAG"
fi

if git ls-remote --tags origin "$TAG" | grep -q "$TAG"; then
  echo "  Tag $TAG already on remote."
else
  echo "  Pushing $TAG to origin ..."
  git push origin "$TAG"
fi

# ---------- compute SHA256 of GitHub archive ----------
ARCHIVE_URL="https://github.com/$GITHUB_USER/$GITHUB_REPO/archive/refs/tags/$TAG.tar.gz"
echo "  Fetching archive: $ARCHIVE_URL"
TMPFILE="$(mktemp /tmp/murmur-XXXXXX.tar.gz)"
trap 'rm -f "$TMPFILE"' EXIT
curl -fsSL "$ARCHIVE_URL" -o "$TMPFILE"
SHA256="$(sha256sum "$TMPFILE" | awk '{print $1}')"
echo "  SHA256: $SHA256"

# ---------- update formula ----------
echo "  Updating formula SHA256 ..."
FORMULA_DEST="$TAP_DIR/Formula/murmur.rb"

# Ensure tap dir exists (clone if needed)
if [[ ! -d "$TAP_DIR/.git" ]]; then
  echo "  Cloning homebrew-murmur tap into $TAP_DIR ..."
  git clone "git@github.com:$GITHUB_USER/homebrew-murmur.git" "$TAP_DIR"
fi

mkdir -p "$(dirname "$FORMULA_DEST")"
cp "$FORMULA_SRC" "$FORMULA_DEST"

# Replace url + sha256 for the current version
sed -i "s|/refs/tags/v[^/]*/|/refs/tags/$TAG/|g" "$FORMULA_DEST"
sed -i "s|sha256 \"[^\"]*\"|sha256 \"$SHA256\"|" "$FORMULA_DEST"

echo "  Updated formula:"
grep -E 'url|sha256' "$FORMULA_DEST" | head -4

# ---------- commit + push tap ----------
cd "$TAP_DIR"
git add Formula/murmur.rb
if git diff --cached --quiet; then
  echo "  Formula unchanged — nothing to commit."
else
  git commit -m "murmur $TAG"
  git push origin HEAD
  echo "  Pushed formula to homebrew-murmur tap."
fi

echo ""
echo "Done! Users can now install with:"
echo "  brew tap $GITHUB_USER/murmur"
echo "  brew install murmur"
