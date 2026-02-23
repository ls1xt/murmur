#!/usr/bin/env bash
# Build a .deb package for murmur-dictation.
#
# Requirements:
#   - fpm: gem install fpm  (or: sudo apt install ruby-dev && sudo gem install fpm)
#   - uv: for building the wheel
#   - A Debian/Ubuntu machine or Docker container
#
# Usage:
#   ./packaging/deb/build-deb.sh
#   # Produces: murmur_0.1.0_amd64.deb in current directory
#
set -euo pipefail

PACKAGE_NAME="murmur"
VERSION="0.1.0"  # Update to match pyproject.toml
ARCH="amd64"
INSTALL_DIR="/opt/murmur"
BIN_DIR="/usr/local/bin"

# Read version from pyproject.toml if available
if command -v python3 &>/dev/null && [[ -f "pyproject.toml" ]]; then
    VERSION=$(python3 -c "
import sys
if sys.version_info >= (3, 11):
    import tomllib
    with open('pyproject.toml', 'rb') as f:
        d = tomllib.load(f)
else:
    try:
        import tomli as tomllib
    except ImportError:
        sys.exit(0)
    with open('pyproject.toml', 'rb') as f:
        d = tomllib.load(f)
print(d['project']['version'])
" 2>/dev/null || echo "${VERSION}")
fi

echo "==> Building murmur ${VERSION} .deb package"

# 1. Build wheel
echo "==> Building wheel"
uv build --wheel
WHEEL=$(ls dist/murmur_dictation-*.whl | sort -V | tail -1)
echo "    Wheel: ${WHEEL}"

# 2. Create staging directory
STAGING=$(mktemp -d)
trap "rm -rf ${STAGING}" EXIT

VENV_DIR="${STAGING}${INSTALL_DIR}"
mkdir -p "${VENV_DIR}"
mkdir -p "${STAGING}${BIN_DIR}"

# 3. Install wheel + all deps into staging virtualenv
echo "==> Installing into staging venv at ${VENV_DIR}"
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --quiet "${WHEEL}"
# Bundled deps (not in Debian repos)
"${VENV_DIR}/bin/pip" install --quiet assemblyai customtkinter

# 4. Create entrypoint wrapper
cat > "${STAGING}${BIN_DIR}/murmur" << 'WRAPPER'
#!/bin/bash
exec /opt/murmur/bin/murmur "$@"
WRAPPER
chmod +x "${STAGING}${BIN_DIR}/murmur"

# 5. Create postinst script
POSTINST=$(mktemp)
cat > "${POSTINST}" << 'POSTINST_SCRIPT'
#!/bin/bash
echo ""
echo "Murmur installed successfully!"
echo ""
echo "Next steps:"
echo "  1. Set your AssemblyAI API key:"
echo "       murmur config --key transcriber.api_key --value YOUR_KEY"
echo "  2. Start the daemon:"
echo "       murmur daemon start"
echo "  3. Enable auto-start (optional):"
echo "       murmur daemon enable"
echo ""
echo "Get an API key at: https://www.assemblyai.com/"
POSTINST_SCRIPT
chmod +x "${POSTINST}"

# 6. Build .deb with fpm
echo "==> Building .deb with fpm"
fpm \
    -s dir \
    -t deb \
    -n "${PACKAGE_NAME}" \
    -v "${VERSION}" \
    -a "${ARCH}" \
    --description "System-wide voice dictation for Linux" \
    --url "https://github.com/ls1xt/murmur" \
    --license "MIT" \
    --depends "python3 (>= 3.10)" \
    --depends "portaudio19-dev" \
    --depends "ydotool" \
    --after-install "${POSTINST}" \
    --chdir "${STAGING}" \
    "opt/murmur=${INSTALL_DIR}" \
    "usr/local/bin/murmur=${BIN_DIR}/murmur"

echo "==> Built: ${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"
echo ""
echo "Install with: sudo dpkg -i ${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"
echo "Uninstall with: sudo dpkg -r ${PACKAGE_NAME}"
