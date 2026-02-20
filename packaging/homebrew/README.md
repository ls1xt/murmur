# Homebrew Formula for Murmur

## Install (once tap is published)

```bash
brew tap berleon/murmur
brew install murmur
```

## Developing

After publishing to PyPI:
1. Update sha256 placeholders using `homebrew-pypi-poet`
2. Submit formula to a personal tap or homebrew-core

```bash
pip install homebrew-pypi-poet
poet -f murmur-dictation
```
