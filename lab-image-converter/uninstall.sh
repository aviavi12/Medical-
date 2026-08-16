#!/usr/bin/env bash
# Uninstall the Lab Image Converter desktop shortcuts and virtual environment.
# Does NOT delete the project files — only removes what install.sh created.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="${HOME}/Desktop"
APPS_DIR="${HOME}/.local/share/applications"
DESKTOP_FILE="labfile-converter.desktop"

echo ""
echo "=== Lab Image Converter — Uninstaller ==="
echo ""

# Stop running server
bash "${SCRIPT_DIR}/stop-server.sh" 2>/dev/null || true

# Remove desktop shortcut
if [ -f "${DESKTOP_DIR}/${DESKTOP_FILE}" ]; then
    rm "${DESKTOP_DIR}/${DESKTOP_FILE}"
    echo "  Removed: ${DESKTOP_DIR}/${DESKTOP_FILE}"
fi

# Remove from applications menu
if [ -f "${APPS_DIR}/${DESKTOP_FILE}" ]; then
    rm "${APPS_DIR}/${DESKTOP_FILE}"
    echo "  Removed: ${APPS_DIR}/${DESKTOP_FILE}"
fi

# Remove virtual environment
if [ -d "${SCRIPT_DIR}/.venv" ]; then
    rm -rf "${SCRIPT_DIR}/.venv"
    echo "  Removed: ${SCRIPT_DIR}/.venv"
fi

# Remove temp files
rm -rf "${SCRIPT_DIR}/uploads/"* 2>/dev/null || true
rm -rf "${SCRIPT_DIR}/outputs/"* 2>/dev/null || true
rm -rf "${SCRIPT_DIR}/__pycache__" 2>/dev/null || true
find "${SCRIPT_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
rm -rf "${SCRIPT_DIR}/.pytest_cache" 2>/dev/null || true

echo ""
echo "  Uninstall complete."
echo "  Project files remain in: ${SCRIPT_DIR}"
echo "  To reinstall:  bash ${SCRIPT_DIR}/install.sh"
echo ""
