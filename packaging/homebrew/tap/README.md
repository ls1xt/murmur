# homebrew-murmur

Homebrew tap for [Murmur](https://github.com/ls1xt/murmur) — system-wide voice dictation for macOS.

## Install

```bash
brew tap ls1xt/murmur
brew install murmur
```

## Development install (latest HEAD)

```bash
brew install --HEAD ls1xt/murmur/murmur
```

## Updating the formula

After tagging a new release in the murmur repo:

```bash
# From the murmur repo root:
./scripts/publish-tap.sh
```

This script computes the new SHA256 from the GitHub release archive and pushes the updated formula to this tap repo.
