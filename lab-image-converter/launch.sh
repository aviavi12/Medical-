#!/usr/bin/env bash
# Laboratory Image Converter — Desktop Launcher
# Starts the server (if not running) and opens the browser.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8000
URL="http://localhost:${PORT}"

# Activate virtual environment
if [ -d "${SCRIPT_DIR}/.venv" ]; then
    source "${SCRIPT_DIR}/.venv/bin/activate"
fi

# Start server if not already running
if ! curl -s --max-time 1 "${URL}/health" >/dev/null 2>&1; then
    cd "$SCRIPT_DIR"

    nohup uvicorn app.main:app --host 127.0.0.1 --port "$PORT" \
        > /tmp/lab-image-converter.log 2>&1 &

    echo "Starting server..."
    for i in $(seq 1 20); do
        sleep 1
        if curl -s --max-time 1 "${URL}/health" >/dev/null 2>&1; then
            echo "Server ready."
            break
        fi
    done
fi

# Open browser
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL"
elif command -v open >/dev/null 2>&1; then
    open "$URL"
elif command -v sensible-browser >/dev/null 2>&1; then
    sensible-browser "$URL"
elif command -v wslview >/dev/null 2>&1; then
    wslview "$URL"
else
    echo ""
    echo "Server running at ${URL}"
    echo "Open this URL in your browser."
fi
