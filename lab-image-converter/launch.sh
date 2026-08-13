#!/usr/bin/env bash
# Laboratory Image Converter — Desktop Launcher
# Opens the web app in the default browser and starts the server if not running.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8000
URL="http://localhost:${PORT}"

if ! curl -s --max-time 1 "${URL}/health" >/dev/null 2>&1; then
    cd "$SCRIPT_DIR"

    if [ -d ".venv" ]; then
        source .venv/bin/activate
    fi

    nohup uvicorn app.main:app --host 127.0.0.1 --port "$PORT" \
        > /tmp/lab-image-converter.log 2>&1 &

    for i in $(seq 1 15); do
        sleep 1
        if curl -s --max-time 1 "${URL}/health" >/dev/null 2>&1; then
            break
        fi
    done
fi

if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL"
elif command -v open >/dev/null 2>&1; then
    open "$URL"
elif command -v sensible-browser >/dev/null 2>&1; then
    sensible-browser "$URL"
else
    echo "Server running at ${URL}"
    echo "Open this URL in your browser."
fi
