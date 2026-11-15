from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.main import app
from app.services.document_analysis import MAX_PDF_BYTES

client = TestClient(app)


def make_text_pdf(*page_texts: str, password: str | None = None) -> bytes:
    writer = PdfWriter()
    for text in page_texts:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        font_ref = writer._add_object(font)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})
        })
        safe_text = text.encode("latin-1", errors="replace").decode("latin-1")
        escaped = safe_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 50 740 Td ({escaped}) Tj ET".encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    if password:
        writer.encrypt(password)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def upload(pdf: bytes, *, content_type: str = "application/pdf", filename: str = "synthetic-offer.pdf"):
    # The route streams raw PDF bytes, so file contents never enter an UploadFile spool.
    return client.post("/api/analyze/document", content=pdf, headers={"Content-Type": content_type, "X-Test-Filename": filename})


def test_legitimate_internship_offer_extracts_text_and_returns_metadata():
    pdf = make_text_pdf(
        "Internship offer. The panel selected you after two interviews. Please confirm the start date in the official careers portal."
    )
    response = upload(pdf)
    assert response.status_code == 200
    result = response.json()
    assert result["risk_level"] == "LOW"
    assert result["document_metadata"] == {
        "page_count": 1,
        "pages_with_text": 1,
        "extraction_status": "text_extracted",
        "size_bytes": len(pdf),
    }
    assert result["analysis_type"] == "ai_hybrid"
    assert "Internship offer" not in response.text
    assert "synthetic-offer.pdf" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_fake_offer_registration_fee_is_high_and_page_aware():
    pdf = make_text_pdf(
        "Internship offer details and responsibilities.",
        "Pay a registration fee today to secure your appointment letter.",
    )
    result = upload(pdf).json()
    assert result["risk_level"] == "HIGH"
    fee = next(f for f in result["findings"] if f["category"] == "Recruitment fee or deposit")
    assert fee["page_number"] == 2
    assert "registration fee" in fee["evidence"].casefold()


def test_payment_finding_quotes_its_own_paragraph_in_multi_paragraph_offer():
    pdf = make_text_pdf(
        "Synthetic offer letter. We are pleased to offer you the Software Intern role at Example Studio.\n\n"
        "To complete onboarding, pay INR 4,999 for the refundable training kit before the offer is issued.\n\n"
        "The payment must arrive within 24 hours or this offer will expire."
    )

    response = upload(pdf)
    assert response.status_code == 200
    result = response.json()
    assert result["risk_level"] == "HIGH"

    payment = next(f for f in result["findings"] if f["category"] == "Candidate-paid recruitment expense")
    urgency = next(f for f in result["findings"] if f["category"] == "Artificial urgency")

    assert "4,999" in payment["evidence"]
    assert "refundable training kit" in payment["evidence"].casefold()
    assert "pleased to offer" not in payment["evidence"].casefold()
    assert payment["page_number"] == 1
    assert "within 24 hours" in urgency["evidence"].casefold()
    assert urgency["page_number"] == 1


def test_identity_and_bank_detail_harvesting_are_detected():
    pdf = make_text_pdf("Upload your Aadhaar and PAN documents and provide your bank account details before the interview.")
    result = upload(pdf).json()
    assert result["risk_level"] == "HIGH"
    categories = {finding["category"] for finding in result["findings"]}
    assert "Identity document request" in categories
    assert "Financial information request" in categories
    assert all(finding["page_number"] == 1 for finding in result["findings"] if finding["category"] in categories)


def test_otp_and_password_harvesting_are_detected():
    pdf = make_text_pdf("Reply with your OTP and password to activate the candidate account.")
    result = upload(pdf).json()
    assert result["risk_level"] == "HIGH"
    assert any(f["category"] == "Password or one-time code request" for f in result["findings"])


def test_ambiguous_offer_flags_short_link_and_internal_inconsistency():
    pdf = make_text_pdf(
        "Company: Juniper Harbor. Start date: 10 June 2027. Continue at https://bit.ly/offer-check.",
        "Employer: Quartz Meadow. Start date: 15 June 2027. Please review the role details.",
    )
    result = upload(pdf).json()
    assert result["risk_level"] == "MEDIUM"
    assert any(f["category"] == "Obscured or messaging-service link" and f["page_number"] == 1 for f in result["findings"])
    assert any(f["category"] == "Inconsistent employer details" for f in result["findings"])
    assert any(f["category"] == "Conflicting offer dates" for f in result["findings"])
    assert "not independently authenticated or opened" in result["disclaimer"]


def test_empty_or_scanned_pdf_returns_explicit_unsupported_error():
    response = upload(make_text_pdf(""))
    assert response.status_code == 422
    assert "Scanned or image-only PDFs are not supported" in response.json()["detail"]


def test_corrupted_pdf_returns_friendly_validation_error():
    response = upload(b"%PDF-1.7\nnot a valid document")
    assert response.status_code == 422
    assert "malformed" in response.json()["detail"].casefold()


def test_non_pdf_mime_signature_and_oversized_uploads_are_rejected():
    pdf = make_text_pdf("Simple synthetic offer text.")
    assert upload(pdf, content_type="text/plain").status_code == 415
    assert upload(b"not a pdf").status_code == 415
    response = upload(b"%PDF-" + b"x" * MAX_PDF_BYTES)
    assert response.status_code == 413
    assert "5 MB" in response.json()["detail"]


def test_password_protected_pdf_is_rejected_without_requesting_password():
    response = upload(make_text_pdf("Confidential synthetic offer", password="synthetic-password"))
    assert response.status_code == 422
    assert "Do not send a document password" in response.json()["detail"]


def test_document_with_page_without_text_is_rejected_instead_of_partial_analysis():
    response = upload(make_text_pdf("Text on page one.", ""))
    assert response.status_code == 422
    assert "at least one page has no selectable text" in response.json()["detail"].casefold()


def test_pdf_evidence_redacts_identity_numbers():
    pdf = make_text_pdf("Upload Aadhaar 1234 5678 9012 and PAN ABCDE1234F before the interview.")
    response = upload(pdf)
    assert response.status_code == 200
    assert "1234 5678 9012" not in response.text
    assert "ABCDE1234F" not in response.text
