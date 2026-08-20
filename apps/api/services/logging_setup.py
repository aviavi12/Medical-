"""Structured logging (§88). Emits JSON lines with contextual fields."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "video_id",
            "person_id",
            "job_id",
            "stage",
            "model",
            "device",
            "elapsed_ms",
            "error",
        ):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str = "silentspeak") -> logging.Logger:
    return logging.getLogger(name)
