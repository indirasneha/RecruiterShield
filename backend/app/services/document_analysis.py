"""In-memory PDF extraction and offer-letter analysis."""

import re
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import urlparse

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.api.schemas import DocumentMetadata, Finding, MessageAnalysisResponse, RiskLevel
from app.services.analyzer import analyze_message

MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 100
MAX_EXTRACTED_CHARS = 80_000


@dataclass
class DocumentAnalysisError(Exception):
    status_code: int
    detail: str


def _extract_pages(pdf_bytes: bytes) -> list[str]:
    if not pdf_bytes.startswith(b"%PDF-"):
        raise DocumentAnalysisError(415, "The uploaded file is not a valid PDF. Choose a PDF offer letter.")
    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=True)
        if reader.is_encrypted:
            raise DocumentAnalysisError(422, "Password-protected PDFs are not supported. Do not send a document password.")
        page_count = len(reader.pages)
        if page_count == 0:
            raise DocumentAnalysisError(422, "This PDF has no pages to analyze.")
        if page_count > MAX_PDF_PAGES:
            raise DocumentAnalysisError(413, f"This PDF has {page_count} pages. The limit is {MAX_PDF_PAGES} pages.")

        page_texts: list[str] = []
        total_chars = 0
        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            total_chars += len(text)
            if total_chars > MAX_EXTRACTED_CHARS:
                raise DocumentAnalysisError(413, "The extracted text exceeds the document analysis limit. Split the offer into smaller PDFs.")
            page_texts.append(text)
        if not any(page_texts):
            raise DocumentAnalysisError(422, "No selectable text could be extracted. Scanned or image-only PDFs are not supported yet; use a text-based PDF.")
        if any(not text for text in page_texts):
            raise DocumentAnalysisError(422, "At least one page has no selectable text. The PDF may contain scanned pages; submit a fully text-based PDF so no page is missed.")
        return page_texts
    except DocumentAnalysisError:
        raise
    except (PdfReadError, EOFError, ValueError, OSError, KeyError, TypeError) as exc:
        raise DocumentAnalysisError(422, "The PDF is malformed or could not be read. Export a fresh, text-based PDF and try again.") from exc
    except Exception as exc:
        # Keep parser failures clear to clients without logging file/text contents.
        raise DocumentAnalysisError(422, "The PDF could not be safely read. Export a fresh, text-based PDF and try again.") from exc


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _page_for_evidence(evidence: str, page_texts: list[str]) -> int | None:
    snippet = evidence.strip("“”\"'")
    normalized = _normalize(snippet)
    if not normalized:
        return None
    for page_number, page_text in enumerate(page_texts, start=1):
        if normalized in _normalize(page_text):
            return page_number
    return None


def _document_specific_findings(page_texts: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    shorteners = {"bit.ly", "tinyurl.com", "t.co", "cutt.ly", "rb.gy", "is.gd", "forms.gle", "t.me", "wa.me"}
    url_pattern = re.compile(r"(?:https?://|www\.)[^\s<>\]\[(){}\"']+", re.IGNORECASE)
    for page_number, page_text in enumerate(page_texts, start=1):
        for raw_url in url_pattern.findall(page_text):
            candidate = raw_url.rstrip(".,;:!?")
            parsed = urlparse(candidate if candidate.lower().startswith(("http://", "https://")) else f"https://{candidate}")
            host = (parsed.hostname or "").casefold()
            if host in shorteners or any(host.endswith(f".{domain}") for domain in shorteners):
                # Do not return query strings, which can contain private tokens.
                safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"[:180]
                findings.append(Finding(
                    category="Obscured or messaging-service link",
                    explanation="This link uses a URL shortener or messaging service, which hides where the link leads. The system did not open it; verify the destination through the employer's official site.",
                    evidence=safe_url,
                    page_number=page_number,
                ))

    company_claims: list[tuple[int, str]] = []
    for page_number, page_text in enumerate(page_texts, start=1):
        for match in re.finditer(r"\b(?:company|employer)\s*(?:name)?\s*:\s*([^\n,;]{2,60})", page_text, re.I):
            claim = re.sub(r"\s+", " ", match.group(1)).strip(" .")
            if claim:
                company_claims.append((page_number, claim))
    if len({claim.casefold() for _, claim in company_claims}) > 1:
        pages = sorted({page for page, _ in company_claims})
        evidence = "; ".join(f"page {page}: {claim[:70]}" for page, claim in company_claims[:3])
        findings.append(Finding(
            category="Inconsistent employer details",
            explanation="The document names more than one employer. This may be a template or editing error, but confirm the offer directly through independently found official channels.",
            evidence=evidence,
            page_number=pages[0] if pages else None,
        ))

    date_claims: list[tuple[int, str]] = []
    date_pattern = re.compile(
        r"\b(?:start|joining|commencement)\s+date\s*(?:is|:|-)?\s*"
        r"((?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})|(?:\d{4}-\d{2}-\d{2})|"
        r"(?:\d{1,2}\s+\w+\s+\d{4})|(?:\w+\s+\d{1,2},?\s+\d{4}))",
        re.I,
    )
    for page_number, page_text in enumerate(page_texts, start=1):
        for match in date_pattern.finditer(page_text):
            date_claims.append((page_number, match.group(1)))
    if len({date.casefold() for _, date in date_claims}) > 1:
        evidence = "; ".join(f"page {page}: start date {date}" for page, date in date_claims[:3])
        findings.append(Finding(
            category="Conflicting offer dates",
            explanation="The document contains different stated start dates. Confirm the correct date with the employer before making plans or sharing information.",
            evidence=evidence,
            page_number=date_claims[0][0],
        ))
    return findings


def analyze_pdf(pdf_bytes: bytes) -> MessageAnalysisResponse:
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise DocumentAnalysisError(413, "The PDF exceeds the 5 MB upload limit.")
    page_texts = _extract_pages(pdf_bytes)
    analysis = analyze_message("\n\n".join(page_texts))
    findings: list[Finding] = []
    for finding in analysis.findings:
        if finding.category == "Overall message pattern":
            finding = finding.model_copy(update={"evidence": "A wording pattern in the extracted document; review the document locally."})
        findings.append(finding.model_copy(update={"page_number": _page_for_evidence(finding.evidence, page_texts)}))
    extra_findings = _document_specific_findings(page_texts)
    findings.extend(extra_findings)

    risk = analysis.risk_level
    if extra_findings and risk == RiskLevel.LOW:
        risk = RiskLevel.MEDIUM
    actions = list(analysis.recommended_actions)
    if any(f.category == "Obscured or messaging-service link" for f in extra_findings):
        actions.append("Do not follow links in the document. Open the employer's official site independently and look up the role there.")
    if any(f.category in {"Inconsistent employer details", "Conflicting offer dates"} for f in extra_findings):
        actions.append("Ask the employer to clarify the conflicting offer details using contact information found independently.")
    return analysis.model_copy(update={
        "risk_level": risk,
        "findings": findings,
        "recommended_actions": list(dict.fromkeys(actions)),
        "disclaimer": analysis.disclaimer + " The document's claims and links were not independently authenticated or opened.",
        "analysis_type": analysis.analysis_type,
        "document_metadata": DocumentMetadata(
            page_count=len(page_texts),
            pages_with_text=sum(bool(text) for text in page_texts),
            extraction_status="text_extracted",
            size_bytes=len(pdf_bytes),
        ),
    })
