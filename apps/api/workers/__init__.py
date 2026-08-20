"""Local in-process workers. Interface stays compatible with Celery + Redis (§5)."""

from apps.api.workers.tasks import process_coarse_scan, process_person_analysis

__all__ = ["process_coarse_scan", "process_person_analysis"]
