# AUR Package for Murmur

Package name: `python-murmur`

## Install

```bash
yay -S python-murmur
# or manually:
git clone https://aur.archlinux.org/python-murmur.git
cd python-murmur
makepkg -si
```

## Publishing to AUR

1. Publish to PyPI first (see scripts/publish.sh)
2. Update sha256sums in PKGBUILD and .SRCINFO
3. Create AUR account and SSH key
4. Clone: `git clone ssh://aur@aur.archlinux.org/python-murmur.git`
5. Copy PKGBUILD + .SRCINFO into the clone
6. Commit and push
