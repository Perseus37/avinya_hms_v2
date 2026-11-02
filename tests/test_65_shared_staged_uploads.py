from io import BytesIO

import pytest

from backend.core.storage import (
    UploadContentError,
    UploadTooLargeError,
    stage_and_publish_upload,
)


def test_staged_upload_publishes_only_after_validation_and_scan(tmp_path):
    events = []
    destination = "a" * 32 + ".pdf"

    def scanner(path):
        events.append(("scan", path.name, path.read_bytes()))

    size = stage_and_publish_upload(
        tmp_path,
        destination,
        "." + destination + ".part",
        BytesIO(b"%PDF-1.7\ninvoice"),
        max_bytes=1024,
        signature=b"%PDF-",
        scanner=scanner,
    )

    assert size == len(b"%PDF-1.7\ninvoice")
    assert events == [("scan", "." + destination + ".part", b"%PDF-1.7\ninvoice")]
    assert (tmp_path / destination).read_bytes() == b"%PDF-1.7\ninvoice"
    assert not (tmp_path / ("." + destination + ".part")).exists()
    assert (tmp_path / destination).stat().st_mode & 0o777 == 0o600


def test_staged_upload_removes_partial_file_when_size_limit_is_exceeded(tmp_path):
    with pytest.raises(UploadTooLargeError):
        stage_and_publish_upload(
            tmp_path,
            "document.pdf",
            ".document.part",
            BytesIO(b"%PDF-123456"),
            max_bytes=5,
            signature=b"%PDF-",
            scanner=lambda _: pytest.fail("scanner must not run"),
        )

    assert list(tmp_path.iterdir()) == []


def test_staged_upload_removes_file_when_signature_is_invalid(tmp_path):
    with pytest.raises(UploadContentError):
        stage_and_publish_upload(
            tmp_path,
            "document.pdf",
            ".document.part",
            BytesIO(b"not a PDF"),
            max_bytes=1024,
            signature=b"%PDF-",
            scanner=lambda _: pytest.fail("scanner must not run"),
        )

    assert list(tmp_path.iterdir()) == []


def test_staged_upload_removes_staged_file_when_scanner_rejects_it(tmp_path):
    def reject(_):
        raise RuntimeError("scanner rejected document")

    with pytest.raises(RuntimeError, match="scanner rejected"):
        stage_and_publish_upload(
            tmp_path,
            "document.pdf",
            ".document.part",
            BytesIO(b"%PDF-1.7"),
            max_bytes=1024,
            signature=b"%PDF-",
            scanner=reject,
        )

    assert list(tmp_path.iterdir()) == []


def test_staged_upload_does_not_remove_an_existing_temp_file_on_collision(tmp_path):
    existing = tmp_path / ".document.part"
    existing.write_bytes(b"owned by another operation")

    with pytest.raises(FileExistsError):
        stage_and_publish_upload(
            tmp_path,
            "document.pdf",
            existing.name,
            BytesIO(b"%PDF-1.7"),
            max_bytes=1024,
            signature=b"%PDF-",
            scanner=lambda _: None,
        )

    assert existing.read_bytes() == b"owned by another operation"
    assert not (tmp_path / "document.pdf").exists()
