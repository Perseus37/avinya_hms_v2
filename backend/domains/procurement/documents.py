import hashlib
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
    UploadEmptyError,
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
    except UploadEmptyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice document cannot be empty.",
        ) from exc
    except UploadContentError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Invoice document content does not match its file type.",
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


def _contract_storage_directory(tenant_slug: str, *, create: bool) -> Path:
    if not _TENANT_SLUG.fullmatch(tenant_slug):
        raise RuntimeError("Tenant slug is not a safe storage path component.")
    try:
        return tenant_storage_directory(
            settings.ATTACHMENTS_STORAGE_DIR,
            tenant_slug,
            "procurement-contracts",
            create=create,
        )
    except StoragePathError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Contract document storage is unavailable.") from exc


def store_supplier_contract_document(
    tenant_slug: str, filename: str | None, source: BinaryIO
) -> tuple[str, Path]:
    if not _TENANT_SLUG.fullmatch(tenant_slug):
        raise RuntimeError("Tenant slug is not a safe storage path component.")
    suffix = Path(filename or "").suffix.lower()
    signature = _ALLOWED_SIGNATURES.get(suffix)
    if signature is None:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail="Contract documents must be PDF, PNG, or JPEG files.")
    tenant_dir = _contract_storage_directory(tenant_slug, create=True)
    document_id = uuid.uuid4().hex
    destination_name = f"{document_id}{suffix}"
    try:
        stage_and_publish_upload(
            tenant_dir, destination_name, f".{document_id}.part", source,
            max_bytes=settings.MAX_ATTACHMENT_UPLOAD_BYTES,
            signature=signature, scanner=scan_file_with_clamav,
        )
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail="Contract document exceeds the configured upload limit.") from exc
    except UploadEmptyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Contract document cannot be empty.") from exc
    except UploadContentError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail="Contract document content does not match its file type.") from exc
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Contract document storage is unavailable.") from exc
    destination = tenant_dir / destination_name
    return PurePosixPath(tenant_slug, "procurement-contracts", destination.name).as_posix(), destination


def resolve_supplier_contract_document(tenant_slug: str, document_key: str) -> Path:
    if not _TENANT_SLUG.fullmatch(tenant_slug):
        raise RuntimeError("Tenant slug is not a safe storage path component.")
    key = PurePosixPath(document_key)
    expected_prefix = PurePosixPath(tenant_slug, "procurement-contracts")
    if (key.is_absolute() or key.parts[:2] != expected_prefix.parts or len(key.parts) != 3
            or not re.fullmatch(r"[0-9a-f]{32}\.(?:pdf|png|jpg|jpeg)", key.name)):
        raise HTTPException(status_code=404, detail="Contract document not found.")
    tenant_dir = _contract_storage_directory(tenant_slug, create=False)
    try:
        path = resolve_tenant_storage_file(tenant_dir, key.name)
    except StoragePathError as exc:
        raise HTTPException(status_code=404, detail="Contract document not found.") from exc
    if path.suffix.lower() not in _ALLOWED_SIGNATURES or not path.is_file():
        raise HTTPException(status_code=404, detail="Contract document not found.")
    return path


def _supplier_compliance_storage_directory(tenant_slug: str, *, create: bool) -> Path:
    if not _TENANT_SLUG.fullmatch(tenant_slug):
        raise RuntimeError("Tenant slug is not a safe storage path component.")
    try:
        return tenant_storage_directory(
            settings.ATTACHMENTS_STORAGE_DIR, tenant_slug,
            "procurement-vendor-compliance", create=create,
        )
    except StoragePathError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Supplier compliance document storage is unavailable.") from exc


def store_supplier_compliance_document(tenant_slug: str, filename: str | None, source: BinaryIO) -> tuple[str, Path]:
    if not _TENANT_SLUG.fullmatch(tenant_slug):
        raise RuntimeError("Tenant slug is not a safe storage path component.")
    suffix = Path(filename or "").suffix.lower()
    signature = _ALLOWED_SIGNATURES.get(suffix)
    if signature is None:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail="Supplier compliance documents must be PDF, PNG, or JPEG files.")
    tenant_dir = _supplier_compliance_storage_directory(tenant_slug, create=True)
    document_id = uuid.uuid4().hex
    destination_name = f"{document_id}{suffix}"
    try:
        stage_and_publish_upload(
            tenant_dir, destination_name, f".{document_id}.part", source,
            max_bytes=settings.MAX_ATTACHMENT_UPLOAD_BYTES,
            signature=signature, scanner=scan_file_with_clamav,
        )
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail="Supplier compliance document exceeds the configured upload limit.") from exc
    except UploadEmptyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Supplier compliance document cannot be empty.") from exc
    except UploadContentError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail="Supplier compliance document content does not match its file type.") from exc
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Supplier compliance document storage is unavailable.") from exc
    destination = tenant_dir / destination_name
    return PurePosixPath(tenant_slug, "procurement-vendor-compliance", destination.name).as_posix(), destination


def resolve_supplier_compliance_document(tenant_slug: str, document_key: str) -> Path:
    if not _TENANT_SLUG.fullmatch(tenant_slug):
        raise RuntimeError("Tenant slug is not a safe storage path component.")
    key = PurePosixPath(document_key)
    expected_prefix = PurePosixPath(tenant_slug, "procurement-vendor-compliance")
    if (key.is_absolute() or key.parts[:2] != expected_prefix.parts or len(key.parts) != 3
            or not re.fullmatch(r"[0-9a-f]{32}\.(?:pdf|png|jpg|jpeg)", key.name)):
        raise HTTPException(status_code=404, detail="Supplier compliance document not found.")
    tenant_dir = _supplier_compliance_storage_directory(tenant_slug, create=False)
    try:
        path = resolve_tenant_storage_file(tenant_dir, key.name)
    except StoragePathError as exc:
        raise HTTPException(status_code=404, detail="Supplier compliance document not found.") from exc
    if path.suffix.lower() not in _ALLOWED_SIGNATURES or not path.is_file():
        raise HTTPException(status_code=404, detail="Supplier compliance document not found.")
    return path




_RECONCILIATION_EVIDENCE_NAMESPACE = "procurement-reconciliation-evidence"


def _reconciliation_evidence_storage_directory(tenant_slug: str, *, create: bool) -> Path:
    if not _TENANT_SLUG.fullmatch(tenant_slug):
        raise RuntimeError("Tenant slug is not a safe storage path component.")
    try:
        return tenant_storage_directory(
            settings.ATTACHMENTS_STORAGE_DIR,
            tenant_slug,
            _RECONCILIATION_EVIDENCE_NAMESPACE,
            create=create,
        )
    except StoragePathError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reconciliation evidence storage is unavailable.",
        ) from exc


def store_reconciliation_evidence(
    tenant_slug: str, filename: str | None, source: BinaryIO
) -> tuple[str, Path, int, str, str]:
    """Publish a scanned PDF/JPEG/PNG evidence file under an opaque tenant key."""
    if not _TENANT_SLUG.fullmatch(tenant_slug):
        raise RuntimeError("Tenant slug is not a safe storage path component.")
    suffix = Path((filename or "").replace(chr(92), "/")).suffix.lower()
    signature = _ALLOWED_SIGNATURES.get(suffix)
    if signature is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Evidence files must be PDF, PNG, or JPEG.",
        )
    tenant_dir = _reconciliation_evidence_storage_directory(tenant_slug, create=True)
    evidence_id = uuid.uuid4().hex
    destination_name = f"{evidence_id}{suffix}"
    try:
        size_bytes = stage_and_publish_upload(
            tenant_dir,
            destination_name,
            f".{evidence_id}.part",
            source,
            max_bytes=settings.MAX_ATTACHMENT_UPLOAD_BYTES,
            signature=signature,
            scanner=scan_file_with_clamav,
        )
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail="Evidence file exceeds the configured upload limit.") from exc
    except UploadEmptyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Evidence file cannot be empty.") from exc
    except UploadContentError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail="Evidence content does not match its file type.") from exc
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Evidence storage is unavailable.") from exc

    destination = tenant_dir / destination_name
    digest = hashlib.sha256()
    with destination.open("rb") as published:
        for chunk in iter(lambda: published.read(1024 * 1024), b""):
            digest.update(chunk)
    media_type = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }[suffix]
    key = PurePosixPath(tenant_slug, _RECONCILIATION_EVIDENCE_NAMESPACE, destination_name).as_posix()
    return key, destination, size_bytes, digest.hexdigest(), media_type


def reconciliation_evidence_sha256(document_path: Path) -> str:
    """Recompute the digest before serving evidence so storage tampering is detected."""
    digest = hashlib.sha256()
    with document_path.open("rb") as document:
        for chunk in iter(lambda: document.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_reconciliation_evidence(tenant_slug: str, document_key: str) -> Path:
    if not _TENANT_SLUG.fullmatch(tenant_slug):
        raise RuntimeError("Tenant slug is not a safe storage path component.")
    key = PurePosixPath(document_key)
    expected_prefix = PurePosixPath(tenant_slug, _RECONCILIATION_EVIDENCE_NAMESPACE)
    if (
        key.is_absolute()
        or key.parts[:2] != expected_prefix.parts
        or len(key.parts) != 3
        or not re.fullmatch(r"[0-9a-f]{32}\\.(?:pdf|png|jpg|jpeg)", key.name)
    ):
        raise HTTPException(status_code=404, detail="Reconciliation evidence not found.")
    tenant_dir = _reconciliation_evidence_storage_directory(tenant_slug, create=False)
    try:
        path = resolve_tenant_storage_file(tenant_dir, key.name)
    except StoragePathError as exc:
        raise HTTPException(status_code=404, detail="Reconciliation evidence not found.") from exc
    if path.suffix.lower() not in _ALLOWED_SIGNATURES or not path.is_file():
        raise HTTPException(status_code=404, detail="Reconciliation evidence not found.")
    return path
