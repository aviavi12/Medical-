"""Model registry endpoint (Phase 22): which VSR models exist, their status,
open-vocabulary flag, license, install state, and which one is active."""

from __future__ import annotations

from fastapi import APIRouter

from ml.common.config import get_ml_config
from ml.common.device import device_report
from ml.lipreading.registry import active_entry, manager_status

router = APIRouter(prefix="/api", tags=["models"])


@router.get("/models")
def list_models() -> dict:
    config = get_ml_config()
    active = active_entry(config)
    return {
        "active_model": active.key if active else config.lip_reading_model,
        "active_open_vocabulary": active.open_vocabulary if active else False,
        "visual_only": True,
        "audio": "IGNORED",
        "device": device_report(config.device),
        "models": manager_status(config),
    }
