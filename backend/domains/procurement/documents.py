import os
import re
import socket
import struct
import uuid
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from fastapi import HTTPException, status

from backend.core.config import settings
from backend.core.storage import (
    StoragePathError,
    UploadContentError,
    UploadTooLargeError,
    resolve_tenant_storage_file,
    stage_and_publish_upload,
    tenant_storage_directory,
)

_ALLOWED_SIGNATURES = {
    ".pdf": b"%PDF-",
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
}
_TENANT_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_CLAMD_CHUNK_SIZE = 64 * 1024
_CLAMD_MAX_RESPONSE_BYTES = 4096


def scan_file_with_clamav(document_path: Path) -> None:
    """Stream a staged document to clamd and fail closed on every non-clean result."""
    try:
        with socket.create_connection(
            (settings.CLAMD_HOST, settings.CLAMD_PORT),
            timeout=settings.CLAMD_TIMEOUT_SECONDS,
        ) as scanner:
            scanner.settimeout(settings.CLAMD_TIMEOUT_SECONDS)
            scanner.sendall(b"zINSTREAM\0")
            with document_path.open("rb") as document:
                while chunk := document.read(_CLAMD_CHUNK_SIZE):
                    scanner.sendall(struct.pack("!I", len(chunk)))
                    scanner.sendall(chunk)
            scanner.sendall(b"\0\0\0\0")

            response = bytearray()
            while b"\0" not in response:
                chunk = scanner.recv(1024)
                if not chunk:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Invoice malware scanner returned no verdict.",
                    )
                response.extend(chunk)
                if len(response) > _CLAMD_MAX_RESPONSE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Invoice malware scanner returned an invalid verdict.",
                    )
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invoice malware scanner is unavailable; the upload was not accepted.",
        ) from exc

    verdict = bytes(response).split(b"\0", 1)[0]
    if verdict == b"stream: OK":
        return
    if verdict.startswith(b"stream: ") and verdict.endswith(b" FOUND"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invoice document failed malware scanning.",
        )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Invoice malware scanner returned an invalid or error verdict.",
    )


def _invoice_storage_directory(tenant_slug: str, *, create: bool) -> Path:
    """Return the shared tenant-safe procurement storage namespace."""
    try:
        return tenant_storage_directory(
            settings.ATTACHMENTS_STORAGE_DIR,
            tenant_slug,
            "procurement-invoices",
            create=create,
        )
    except StoragePathError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invoice document storage is unavailable.",
        ) from exc


def store_vendor_invoice_document(
    tenant_slug: str, filename: str | None, source: BinaryIO
) -> tuple[str, Path]:
    """Store a bounded, signature-checked invoice under an unguessable tenant key."""
    if not _TENANT_SLUG.fullmatch(tenant_slug):
        raise RuntimeError("Tenant slug is not a safe storage path component.")

    suffix = Path(filename or "").suffix.lower()
    signature = _ALLOWED_SIGNATURES.get(suffix)
    if signature is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Invoice documents must be PDF, PNG, or JPEG files.",
        )

    tenant_dir = _invoice_storage_directory(tenant_slug, create=True)
    document_id = uuid.uuid4().hex
    destination_name = f"{document_id}{suffix}"
    temporary_name = f".{document_id}.part"

    try:
        stage_and_publish_upload(
            tenant_dir,
            destination_name,
            temporary_name,
            source,
            max_bytes=settings.MAX_ATTACHMENT_UPLOAD_BYTES,
            signature=signature,
            scanner=scan_file_with_clamav,
        )
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Invoice document exceeds the configured upload limit.",
        ) from exc
    except UploadContentError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Invoice document content does not match its file type or is empty.",
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invoice document storage is unavailable.",
        ) from exc

    destination = tenant_dir / destination_name
    key = PurePosixPath(tenant_slug, "procurement-invoices", destination.name).as_posix()
    return key, destination
def resolve_vendor_invoice_document(tenant_slug: str, document_key: str) -> Path:
    """Resolve a stored invoice key while enforcing tenant and symlink boundaries."""
    if not _TENANT_SLUG.fullmatch(tenant_slug):
        raise RuntimeError("Tenant slug is not a safe storage path component.")

    key = PurePosixPath(document_key)
    expected_prefix = PurePosixPath(tenant_slug, "procurement-invoices")
    if (
        key.is_absolute()
        or key.parts[:2] != expected_prefix.parts
        or len(key.parts) != 3
        or not re.fullmatch(r"[0-9a-f]{32}\.(?:pdf|png|jpg|jpeg)", key.name)
    ):
        raise HTTPException(status_code=404, detail="Invoice document not found.")

    tenant_dir = _invoice_storage_directory(tenant_slug, create=False)
    try:
        document_path = resolve_tenant_storage_file(tenant_dir, key.name)
    except StoragePathError as exc:
        raise HTTPException(status_code=404, detail="Invoice document not found.") from exc

    if document_path.suffix.lower() not in _ALLOWED_SIGNATURES or not document_path.is_file():
        raise HTTPException(status_code=404, detail="Invoice document not found.")
    return document_path
