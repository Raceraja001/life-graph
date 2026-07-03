"""MinIO (S3-compatible) object storage client.

Wraps the ``minio`` Python SDK to provide a simple interface for
uploading, downloading, listing, and deleting objects in MinIO buckets.

Configuration is pulled from :mod:`life_graph.config` by default, but
all parameters can be overridden at construction time.

Usage::

    from life_graph.storage.minio_client import MinIOStorage

    storage = MinIOStorage()
    storage.ensure_bucket("voice-notes")
    url = storage.upload("voice-notes", "recording.wav", audio_bytes, "audio/wav")
"""

from __future__ import annotations

import io
import logging
from typing import Any

from life_graph.config import settings

logger = logging.getLogger(__name__)


class MinIOStorage:
    """Client for MinIO / S3-compatible object storage.

    Args:
        endpoint: MinIO server address (``host:port``).
        access_key: Access key (username).
        secret_key: Secret key (password).
        secure: Whether to use HTTPS.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        secure: bool = False,
    ) -> None:
        try:
            from minio import Minio
        except ImportError as exc:
            raise ImportError(
                "The 'minio' package is required for object storage. "
                "Install it with: pip install minio"
            ) from exc

        self.client = Minio(
            endpoint or settings.minio_endpoint,
            access_key=access_key or settings.minio_access_key,
            secret_key=secret_key or settings.minio_secret_key,
            secure=secure,
        )
        self._endpoint = endpoint or settings.minio_endpoint
        self._secure = secure

    def ensure_bucket(self, bucket: str) -> None:
        """Create the bucket if it does not already exist.

        Args:
            bucket: Name of the bucket to create.
        """
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)
            logger.info("Created MinIO bucket: %s", bucket)
        else:
            logger.debug("MinIO bucket already exists: %s", bucket)

    def upload(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload bytes to a bucket and return the object URL.

        Args:
            bucket: Target bucket name.
            key: Object key (path within the bucket).
            data: Raw bytes to upload.
            content_type: MIME type of the object.

        Returns:
            The URL string for the uploaded object.
        """
        self.ensure_bucket(bucket)
        stream = io.BytesIO(data)
        self.client.put_object(
            bucket,
            key,
            stream,
            length=len(data),
            content_type=content_type,
        )
        url = self.get_url(bucket, key)
        logger.info("Uploaded %s/%s (%d bytes)", bucket, key, len(data))
        return url

    def download(self, bucket: str, key: str) -> bytes:
        """Download an object from MinIO and return its raw bytes.

        Args:
            bucket: Bucket name.
            key: Object key.

        Returns:
            The raw bytes of the object.
        """
        response = None
        try:
            response = self.client.get_object(bucket, key)
            data = response.read()
            logger.debug("Downloaded %s/%s (%d bytes)", bucket, key, len(data))
            return data
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def list_objects(self, bucket: str, prefix: str = "") -> list[dict[str, Any]]:
        """List objects in a bucket, optionally filtered by prefix.

        Args:
            bucket: Bucket name.
            prefix: Key prefix to filter by.

        Returns:
            List of dicts with ``key``, ``size``, ``last_modified``, and
            ``content_type`` for each matching object.
        """
        objects = self.client.list_objects(bucket, prefix=prefix, recursive=True)
        results: list[dict[str, Any]] = []
        for obj in objects:
            results.append({
                "key": obj.object_name,
                "size": obj.size,
                "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                "content_type": obj.content_type,
            })
        return results

    def delete(self, bucket: str, key: str) -> bool:
        """Delete an object from MinIO.

        Args:
            bucket: Bucket name.
            key: Object key to delete.

        Returns:
            ``True`` if the deletion was attempted (MinIO does not
            distinguish between deleting an existing vs non-existing object).
        """
        try:
            self.client.remove_object(bucket, key)
            logger.info("Deleted %s/%s", bucket, key)
            return True
        except Exception:
            logger.exception("Failed to delete %s/%s", bucket, key)
            return False

    def get_url(self, bucket: str, key: str) -> str:
        """Build the URL for an object (unsigned, assumes public or internal access).

        Args:
            bucket: Bucket name.
            key: Object key.

        Returns:
            URL string in the form ``http(s)://endpoint/bucket/key``.
        """
        scheme = "https" if self._secure else "http"
        return f"{scheme}://{self._endpoint}/{bucket}/{key}"
