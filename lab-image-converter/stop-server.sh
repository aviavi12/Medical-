#!/usr/bin/env bash
# Stop the Lab Image Converter server.

PIDS=$(pgrep -f "uvicorn app.main:app" 2>/dev/null)

if [ -z "$PIDS" ]; then
    echo "Server is not running."
else
    echo "Stopping server (PID: ${PIDS})..."
    kill $PIDS 2>/dev/null
    sleep 1
    # Force kill if still running
    for pid in $PIDS; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
        fi
    done
    echo "Server stopped."
fi
