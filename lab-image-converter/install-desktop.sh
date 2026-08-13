#!/usr/bin/env bash
# Install the Lab Image Converter desktop shortcut.
# Run from inside the lab-image-converter directory:
#   bash install-desktop.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="${HOME}/Desktop"
APPS_DIR="${HOME}/.local/share/applications"
DESKTOP_FILE="lab-image-converter.desktop"

echo "=== Lab Image Converter — Desktop Installer ==="
echo ""
echo "Project directory: ${SCRIPT_DIR}"

# 1. Make sure launch.sh is executable
chmod +x "${SCRIPT_DIR}/launch.sh"

# 2. Generate the .desktop file with the real path (template stays clean in git)
TEMPLATE="${SCRIPT_DIR}/${DESKTOP_FILE}"
GENERATED="/tmp/${DESKTOP_FILE}"
sed "s|INSTALL_DIR_PLACEHOLDER|${SCRIPT_DIR}|g" "$TEMPLATE" > "$GENERATED"

# 3. Copy to Desktop
mkdir -p "$DESKTOP_DIR"
cp "$GENERATED" "${DESKTOP_DIR}/${DESKTOP_FILE}"
chmod +x "${DESKTOP_DIR}/${DESKTOP_FILE}"

# Mark as trusted (GNOME/Ubuntu)
if command -v gio >/dev/null 2>&1; then
    gio set "${DESKTOP_DIR}/${DESKTOP_FILE}" metadata::trusted true 2>/dev/null || true
fi

# 4. Copy to applications menu
mkdir -p "$APPS_DIR"
cp "$GENERATED" "${APPS_DIR}/${DESKTOP_FILE}"

echo ""
echo "Done!"
echo ""
echo "  Desktop shortcut:  ${DESKTOP_DIR}/${DESKTOP_FILE}"
echo "  Applications menu: ${APPS_DIR}/${DESKTOP_FILE}"
echo ""
echo "Double-click the icon on your Desktop to start."
echo "The server will launch automatically and open your browser."
