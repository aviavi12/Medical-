#!/usr/bin/env bash
###############################################################################
# Lab Image Converter — Build Portable Package
#
# Creates a self-contained .tar.gz that can be copied to any Linux machine
# (same architecture) and installed without internet access.
#
# What it does:
#   1. Downloads all Python wheel files into offline-packages/
#   2. Bundles the entire project into a .tar.gz archive
#
# The resulting archive contains everything needed:
#   - All source code
#   - All Python dependencies (as wheel files)
#   - install.sh (full installer)
#   - launch.sh, stop-server.sh, uninstall.sh
#   - Desktop shortcut template and icon
#
# Usage:
#   bash build-package.sh
#
# On the target machine:
#   tar xzf lab-image-converter-portable.tar.gz
#   cd lab-image-converter
#   bash install.sh
###############################################################################
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OFFLINE_DIR="${SCRIPT_DIR}/offline-packages"
PACKAGE_NAME="lab-image-converter-portable"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}  Building Portable Package${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

########################################
# Step 1: Download all wheels
########################################
echo -e "${YELLOW}[1/3]${NC} Downloading Python packages for offline install..."

rm -rf "$OFFLINE_DIR"
mkdir -p "$OFFLINE_DIR"

pip download \
    -r "${SCRIPT_DIR}/requirements.txt" \
    --dest "$OFFLINE_DIR" \
    --quiet

WHEEL_COUNT=$(ls -1 "$OFFLINE_DIR" | wc -l)
echo -e "  ${GREEN}Downloaded ${WHEEL_COUNT} packages.${NC}"

########################################
# Step 2: Clean up build artifacts
########################################
echo -e "${YELLOW}[2/3]${NC} Cleaning temporary files..."

find "${SCRIPT_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
rm -rf "${SCRIPT_DIR}/.pytest_cache" 2>/dev/null || true
rm -f "${SCRIPT_DIR}/uploads/"*.* 2>/dev/null || true
rm -f "${SCRIPT_DIR}/outputs/"*.* 2>/dev/null || true

echo "  Clean."

# Convert Windows scripts to CRLF line endings
for f in "${SCRIPT_DIR}"/*.cmd "${SCRIPT_DIR}"/*.bat "${SCRIPT_DIR}"/*.ps1; do
    [ -f "$f" ] && sed -i 's/$/\r/' "$f" 2>/dev/null || true
done
echo "  Windows line endings applied to .cmd/.bat/.ps1 files."

########################################
# Step 3: Create archive
########################################
echo -e "${YELLOW}[3/3]${NC} Creating archive..."

cd "${SCRIPT_DIR}/.."
ARCHIVE="${SCRIPT_DIR}/../${PACKAGE_NAME}.tar.gz"

tar czf "$ARCHIVE" \
    --exclude='.venv' \
    --exclude='.git' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='*.tar.gz' \
    "$(basename "$SCRIPT_DIR")"

# Move archive into the project directory for convenience
mv "$ARCHIVE" "${SCRIPT_DIR}/${PACKAGE_NAME}.tar.gz"
ARCHIVE="${SCRIPT_DIR}/${PACKAGE_NAME}.tar.gz"

ARCHIVE_SIZE=$(du -h "$ARCHIVE" | cut -f1)

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  Package Built Successfully${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "  Archive:  ${ARCHIVE}"
echo "  Size:     ${ARCHIVE_SIZE}"
echo ""
echo "  To install on another machine:"
echo ""
echo "    1. Copy ${PACKAGE_NAME}.tar.gz to the target machine"
echo "    2. tar xzf ${PACKAGE_NAME}.tar.gz"
echo "    3. cd lab-image-converter"
echo "    4. bash install.sh"
echo ""
echo "  The only prerequisite on the target machine is Python 3.10+"
echo "  (with python3-venv). No internet connection is needed."
echo ""
