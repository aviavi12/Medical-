"""StorageProvider abstraction (§60).

Local filesystem in development; S3-compatible object storage in production.
Business logic depends only on the interface, never on the filesystem directly.
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from apps.api.config import Settings, get_settings


class StorageError(RuntimeError):
    pass


class StorageProvider(ABC):
    @abstractmethod
    def save(self, key: str, source_path: str | Path) -> str:
        """Persist a file under ``key``; return the canonical storage path/uri."""

    @abstractmethod
    def save_bytes(self, key: str, data: bytes) -> str: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def local_path(self, key: str) -> Path:
        """A concrete local path for processing (may download in S3 impl)."""

    @abstractmethod
    def delete(self, key: str) -> bool: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def generate_url(self, key: str) -> str: ...


class LocalStorage(StorageProvider):
    """Filesystem-backed storage with path-traversal protection (§61)."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Prevent path traversal: the resolved path must stay under root.
        candidate = (self.root / key).resolve()
        if not str(candidate).startswith(str(self.root)):
            raise StorageError(f"Unsafe storage key rejected: {key!r}")
        return candidate

    def save(self, key: str, source_path: str | Path) -> str:
        dest = self._resolve(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, dest)
        return str(dest)

    def save_bytes(self, key: str, data: bytes) -> str:
        dest = self._resolve(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest)

    def get(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def local_path(self, key: str) -> Path:
        return self._resolve(key)

    def delete(self, key: str) -> bool:
        p = self._resolve(key)
        if p.exists():
            p.unlink()
            return True
        return False

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def generate_url(self, key: str) -> str:
        # Served through the API's media endpoint in dev.
        return f"/media/{key}"


class S3Storage(StorageProvider):
    """S3-compatible storage. Raises a clear error until configured/installed."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        try:
            import boto3  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on optional dep
            raise StorageError(
                "S3 storage requires boto3. Install it and set S3_* env vars, "
                "or use STORAGE_BACKEND=local."
            ) from exc
        if not settings.s3_bucket:
            raise StorageError("STORAGE_BACKEND=s3 but S3_BUCKET is not set.")
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region or None,
            aws_access_key_id=settings.s3_access_key_id or None,
            aws_secret_access_key=settings.s3_secret_access_key or None,
        )

    def save(self, key: str, source_path: str | Path) -> str:  # pragma: no cover
        self._client.upload_file(str(source_path), self.settings.s3_bucket, key)
        return f"s3://{self.settings.s3_bucket}/{key}"

    def save_bytes(self, key: str, data: bytes) -> str:  # pragma: no cover
        self._client.put_object(Bucket=self.settings.s3_bucket, Key=key, Body=data)
        return f"s3://{self.settings.s3_bucket}/{key}"

    def get(self, key: str) -> bytes:  # pragma: no cover
        obj = self._client.get_object(Bucket=self.settings.s3_bucket, Key=key)
        return obj["Body"].read()

    def local_path(self, key: str) -> Path:  # pragma: no cover
        raise StorageError("S3 local_path requires downloading to a temp dir (not implemented in MVP).")

    def delete(self, key: str) -> bool:  # pragma: no cover
        self._client.delete_object(Bucket=self.settings.s3_bucket, Key=key)
        return True

    def exists(self, key: str) -> bool:  # pragma: no cover
        try:
            self._client.head_object(Bucket=self.settings.s3_bucket, Key=key)
            return True
        except Exception:
            return False

    def generate_url(self, key: str) -> str:  # pragma: no cover
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self.settings.s3_bucket, "Key": key}, ExpiresIn=3600
        )


def get_storage(settings: Settings | None = None) -> StorageProvider:
    settings = settings or get_settings()
    if settings.storage_backend == "s3":
        return S3Storage(settings)
    return LocalStorage(settings.storage_root)
