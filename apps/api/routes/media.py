"""Media serving (dev). Serves stored files (video, thumbnails, audio) locally.

Path-traversal safe via the storage provider's key resolution. In production the
StorageProvider generates signed URLs instead (§60).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from apps.api.dependencies import get_storage_provider
from apps.api.services.storage import LocalStorage, StorageError, StorageProvider

router = APIRouter(tags=["media"])


@router.get("/media/{key:path}")
def get_media(key: str, storage: StorageProvider = Depends(get_storage_provider)):
    if not isinstance(storage, LocalStorage):  # pragma: no cover
        raise HTTPException(status_code=404, detail="Media served via signed URLs in this backend.")
    try:
        path = storage.local_path(key)
    except StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Media not found.")
    # FileResponse supports HTTP range requests for smooth video seeking.
    return FileResponse(str(path))
