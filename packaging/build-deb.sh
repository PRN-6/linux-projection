#!/bin/sh
# Build a .deb package for Debian/Ubuntu.
#
# Requires: dpkg-deb (from the dpkg package), fakeroot is optional.
set -eu

VERSION="${VERSION:-$(python3 -c 'import re,sys;print(re.search(r"version = \"(.*)\"", open("pyproject.toml").read()).group(1))')}"
ARCH="${ARCH:-$(dpkg --print-architecture)}"
NAME="sereen"
BUILD_DIR="build/deb/${NAME}_${VERSION}_${ARCH}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Building ${NAME} ${VERSION} for ${ARCH}"
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}/DEBIAN"
mkdir -p "${BUILD_DIR}/usr/lib/python3/dist-packages"
mkdir -p "${BUILD_DIR}/usr/bin"
mkdir -p "${BUILD_DIR}/usr/share/applications"
mkdir -p "${BUILD_DIR}/usr/share/metainfo"
mkdir -p "${BUILD_DIR}/usr/share/doc/${NAME}"

# Install the package source into dist-packages.
cp -r "${REPO_ROOT}/src/sereen" "${BUILD_DIR}/usr/lib/python3/dist-packages/"

# The console script.
cat > "${BUILD_DIR}/usr/bin/${NAME}" <<'EOF'
#!/usr/bin/python3
import re
import sys
from sereen.cli import main
if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
    sys.exit(main())
EOF
chmod 755 "${BUILD_DIR}/usr/bin/${NAME}"

cat > "${BUILD_DIR}/DEBIAN/control" <<EOF
Package: ${NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: python3 (>= 3.10)
Maintainer: sereen contributors
Homepage: https://github.com/example/sereen-project-linux
Description: Discover and control Epson projectors
 A dependency-free Linux client for Epson projectors. Finds projectors on the
 local network over PJLink, ESC/VP.net, SSDP and mDNS, and controls power,
 input source, volume and mute.
EOF

cat > "${BUILD_DIR}/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
# Remove stale bytecode from previous versions.
find /usr/lib/python3/dist-packages/sereen -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
exit 0
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/postinst"

cp "${REPO_ROOT}/README.md" "${BUILD_DIR}/usr/share/doc/${NAME}/README.md"
cp "${REPO_ROOT}/LICENSE" "${BUILD_DIR}/usr/share/doc/${NAME}/LICENSE" 2>/dev/null || true

dpkg-deb --build --root-owner-group "${BUILD_DIR}" "${REPO_ROOT}/build/${NAME}_${VERSION}_${ARCH}.deb"
echo "==> ${REPO_ROOT}/build/${NAME}_${VERSION}_${ARCH}.deb"
