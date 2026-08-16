#!/usr/bin/env bash
###############################################################################
# Lab Image Converter — Full Installer
#
# This script does everything needed to run the application on a new machine:
#   1. Checks that Python 3.10+ is installed
#   2. Creates a virtual environment inside this directory
#   3. Installs all Python dependencies (offline if wheels are bundled)
#   4. Creates uploads/ and outputs/ directories
#   5. Installs a desktop shortcut and application-menu entry
#   6. Verifies the installation works
#
# Usage:
#   cd lab-image-converter
#   bash install.sh
#
# The entire folder is portable — copy it to another machine and run
# install.sh again. No internet is needed if the offline-packages/
# directory contains pre-downloaded wheels (see build-package.sh).
###############################################################################
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
DESKTOP_DIR="${HOME}/Desktop"
APPS_DIR="${HOME}/.local/share/applications"
DESKTOP_FILE="labfile-converter.desktop"
OFFLINE_DIR="${SCRIPT_DIR}/offline-packages"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}  LabFile Converter — Installer${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

########################################
# Step 1: Check Python
########################################
echo -e "${YELLOW}[1/6]${NC} Checking Python..."

PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        major=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null)
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}ERROR: Python 3.10 or higher is required.${NC}"
    echo ""
    echo "Install Python:"
    echo "  Ubuntu/Debian:  sudo apt install python3 python3-venv python3-pip"
    echo "  Fedora:         sudo dnf install python3"
    echo "  macOS:          brew install python@3.12"
    echo "  Windows:        https://www.python.org/downloads/"
    exit 1
fi

echo -e "  Found: ${GREEN}${PYTHON_CMD} ${version}${NC}"

# Check venv module
if ! "$PYTHON_CMD" -c "import venv" 2>/dev/null; then
    echo -e "${RED}ERROR: Python venv module not found.${NC}"
    echo "  Install it:  sudo apt install python3-venv"
    exit 1
fi

########################################
# Step 2: Create virtual environment
########################################
echo -e "${YELLOW}[2/6]${NC} Creating virtual environment..."

if [ -d "$VENV_DIR" ]; then
    echo "  Virtual environment already exists. Reusing."
else
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    echo -e "  Created: ${GREEN}${VENV_DIR}${NC}"
fi

source "${VENV_DIR}/bin/activate"

########################################
# Step 3: Install dependencies
########################################
echo -e "${YELLOW}[3/6]${NC} Installing dependencies..."

pip install --upgrade pip --quiet 2>/dev/null

if [ -d "$OFFLINE_DIR" ] && [ "$(ls -A "$OFFLINE_DIR" 2>/dev/null)" ]; then
    echo "  Using offline packages from: ${OFFLINE_DIR}"
    pip install --no-index --find-links "$OFFLINE_DIR" -r "${SCRIPT_DIR}/requirements.txt" --quiet
else
    echo "  Downloading from PyPI (internet required)..."
    pip install -r "${SCRIPT_DIR}/requirements.txt" --quiet
fi

echo -e "  ${GREEN}Dependencies installed.${NC}"

########################################
# Step 4: Create directories
########################################
echo -e "${YELLOW}[4/6]${NC} Creating work directories..."

mkdir -p "${SCRIPT_DIR}/uploads"
mkdir -p "${SCRIPT_DIR}/outputs"
echo "  uploads/ and outputs/ ready."

########################################
# Step 5: Desktop shortcut
########################################
echo -e "${YELLOW}[5/6]${NC} Installing desktop shortcut..."

chmod +x "${SCRIPT_DIR}/launch.sh"
chmod +x "${SCRIPT_DIR}/stop-server.sh" 2>/dev/null || true

TEMPLATE="${SCRIPT_DIR}/${DESKTOP_FILE}"
GENERATED="/tmp/${DESKTOP_FILE}"
sed "s|INSTALL_DIR_PLACEHOLDER|${SCRIPT_DIR}|g" "$TEMPLATE" > "$GENERATED"

mkdir -p "$DESKTOP_DIR"
cp "$GENERATED" "${DESKTOP_DIR}/${DESKTOP_FILE}"
chmod +x "${DESKTOP_DIR}/${DESKTOP_FILE}"

if command -v gio >/dev/null 2>&1; then
    gio set "${DESKTOP_DIR}/${DESKTOP_FILE}" metadata::trusted true 2>/dev/null || true
fi

mkdir -p "$APPS_DIR"
cp "$GENERATED" "${APPS_DIR}/${DESKTOP_FILE}"

echo -e "  ${GREEN}Shortcut installed on Desktop.${NC}"

########################################
# Step 6: Verify installation
########################################
echo -e "${YELLOW}[6/6]${NC} Verifying installation..."

VERIFY_OK=true

"$PYTHON_CMD" -c "import fastapi" 2>/dev/null || VERIFY_OK=false
"$PYTHON_CMD" -c "import uvicorn" 2>/dev/null || VERIFY_OK=false
"$PYTHON_CMD" -c "import PIL" 2>/dev/null || VERIFY_OK=false
"$PYTHON_CMD" -c "import numpy" 2>/dev/null || VERIFY_OK=false
"$PYTHON_CMD" -c "import tifffile" 2>/dev/null || VERIFY_OK=false
"$PYTHON_CMD" -c "import aicspylibczi" 2>/dev/null || VERIFY_OK=false

if [ "$VERIFY_OK" = true ]; then
    echo -e "  ${GREEN}All packages verified.${NC}"
else
    echo -e "  ${RED}Some packages failed to import. Check the log above.${NC}"
    exit 1
fi

########################################
# Done
########################################
echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "  Location:   ${SCRIPT_DIR}"
echo "  Desktop:    ${DESKTOP_DIR}/${DESKTOP_FILE}"
echo ""
echo "  How to start:"
echo "    Option 1:  Double-click the 'LabFile Converter' icon on your Desktop"
echo "    Option 2:  bash ${SCRIPT_DIR}/launch.sh"
echo "    Option 3:  cd ${SCRIPT_DIR} && source .venv/bin/activate && uvicorn app.main:app --reload"
echo ""
echo "  How to stop:"
echo "    bash ${SCRIPT_DIR}/stop-server.sh"
echo ""
echo "  Open in browser:  http://localhost:8000"
echo ""
