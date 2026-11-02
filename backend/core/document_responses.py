"""Safe HTTP responses for generated downloadable documents."""

import re

from fastapi.responses import Response


def pdf_attachment_response(content: bytes, filename: str) -> Response:
    """Return a non-cacheable PDF attachment with a sanitized ASCII filename."""
    safe_filename = re.sub(r"[^A-Za-z0-9._-]", "_", filename or "document.pdf")
    safe_filename = safe_filename.strip("._") or "document"
    if not safe_filename.lower().endswith(".pdf"):
        safe_filename = f"{safe_filename}.pdf"

    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
            "X-Download-Options": "noopen",
            "Cross-Origin-Resource-Policy": "same-origin",
        },
    )
