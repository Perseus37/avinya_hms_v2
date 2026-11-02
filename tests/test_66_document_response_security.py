from backend.core.document_responses import pdf_attachment_response


def test_pdf_attachment_response_disables_caching_and_sets_security_headers():
    response = pdf_attachment_response(b"%PDF-test", "invoice-123.pdf")

    assert response.status_code == 200
    assert response.media_type == "application/pdf"
    assert response.body == b"%PDF-test"
    assert response.headers["content-disposition"] == 'attachment; filename="invoice-123.pdf"'
    assert response.headers["cache-control"] == "private, no-store, max-age=0"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-download-options"] == "noopen"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"


def test_pdf_attachment_response_sanitizes_untrusted_filename_characters():
    response = pdf_attachment_response(b"%PDF-test", '../../invoice\r\nX-Evil: yes')

    assert response.headers["content-disposition"] == 'attachment; filename="invoice_X-Evil__yes.pdf"'
    assert "\r" not in response.headers["content-disposition"]
    assert "\n" not in response.headers["content-disposition"]


def test_pdf_attachment_response_adds_pdf_extension():
    response = pdf_attachment_response(b"%PDF-test", "claim-123")

    assert response.headers["content-disposition"] == 'attachment; filename="claim-123.pdf"'
