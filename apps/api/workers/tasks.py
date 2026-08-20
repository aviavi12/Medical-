"""Worker tasks.

Each task opens its own DB session (so it is safe to run in a background thread
or, later, a Celery worker). Tasks take IDs, never ORM objects bound to a
request-scoped session.
"""

from __future__ import annotations

from apps.api.config import get_settings
from apps.api.services import pipeline
from apps.api.services.storage import get_storage
from database import models
from database.base import get_session_factory
from ml.common.config import get_ml_config


def process_coarse_scan(video_id: str) -> None:
    settings = get_settings()
    config = get_ml_config()
    storage = get_storage(settings)
    factory = get_session_factory()
    db = factory()
    try:
        video = db.get(models.Video, video_id)
        if video is None:
            return
        pipeline.run_coarse_scan(db, video, storage, settings, config)
    finally:
        db.close()


def process_person_analysis(video_id: str, person_id: str, override_gates: bool = False) -> dict | None:
    settings = get_settings()
    config = get_ml_config()
    storage = get_storage(settings)
    factory = get_session_factory()
    db = factory()
    try:
        video = db.get(models.Video, video_id)
        person = db.get(models.PersonTrack, person_id)
        if video is None or person is None:
            return None
        return pipeline.run_person_analysis(db, video, person, storage, settings, config, override_gates)
    finally:
        db.close()
