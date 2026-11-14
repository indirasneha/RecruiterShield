"""Hybrid ML and explainable signal analysis with an explicit missing-model fallback."""

from functools import lru_cache
from pathlib import Path
import re

from app.api.schemas import Finding, MessageAnalysisResponse, RiskLevel
from app.ml.model import default_model_path
from app.services.signals import Signal, detect_signals, is_benign_recruitment_context

DISCLAIMER = (
    "This is a risk assessment of message content and does not independently verify the recruiter or company. "
    "Confirm opportunities through contact details you find independently on the employer's official site."
)
FALLBACK_DISCLAIMER = (
    "The trained text model is unavailable, so this result uses contextual rule checks only. "
    "This assessment does not independently verify the recruiter or company. Confirm through independently found official channels."
)


@lru_cache(maxsize=1)
def _load_model(path_string: str):
    path = Path(path_string)
    if not path.is_file():
        return None
    try:
        # joblib artifacts are project-owned, locally generated model files.
        import joblib
        model = joblib.load(path)
        if not hasattr(model, "predict"):
            return None
        return model
    except Exception:
        # Loading failures are surfaced to clients by analysis_type and disclaimer;
        # no input or exception content is logged.
        return None


def _redact_evidence(value: str) -> str:
    # Evidence should show the suspicious request without reflecting private
    # identifiers copied into the same sentence or PDF page.
    value = re.sub(r"\b[A-Z]{5}\d{4}[A-Z]\b", "[redacted ID]", value, flags=re.I)
    value = re.sub(r"\b(?:\d[ -]?){12}\b", "[redacted ID number]", value)
    value = re.sub(r"\b\d{8,}\b", "[redacted number]", value)
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted email]", value)
    value = re.sub(r"https?://[^\s]+", lambda m: re.sub(r"([?#]).*$", r"\1[redacted]", m.group(0)), value, flags=re.I)
    return value[:180]


def _quote_finding(signal: Signal) -> Finding:
    return Finding(category=signal.category, explanation=signal.explanation, evidence=f'“{_redact_evidence(signal.evidence)}”')


def _risk_from_hybrid(predicted: str, signals: list[Signal], benign_context: bool) -> RiskLevel:
    active = [signal for signal in signals if signal.severity > 0]
    categories = {signal.category for signal in active}
    # Direct credential, candidate-payment, or financial-detail requests are
    # dangerous even when the same message also mentions a normal interview.
    direct_danger = bool(categories & {
        "Password or one-time code request",
        "Financial information request",
        "Recruitment fee or deposit",
        "Candidate-paid recruitment expense",
    })
    if direct_danger:
        return RiskLevel.HIGH
    # Identity harvesting paired with coercion, secrecy, premature selection,
    # another sensitive request, or an unresolved expense is high risk. Secure
    # post-offer requests are severity zero and do not take this path.
    if any(signal.category == "Identity document request" for signal in active):
        corroborating = categories & {
            "Financial information request", "Candidate-paid recruitment expense", "Unclear recruitment expense",
            "Artificial urgency", "Offer cancellation pressure", "Secrecy or blocked verification",
            "Unusual selection claim", "Password or one-time code request",
        }
        if corroborating or len(active) >= 2:
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM
    # Separate caution signals together outweigh unrelated benign wording.
    if len(active) >= 2:
        return RiskLevel.HIGH
    if active:
        return RiskLevel.MEDIUM
    # A safe post-offer document/payroll context can counter a model-only high
    # prediction. Ordinary interview/resume words cannot erase an unsupported
    # high prediction; that result is retained as MEDIUM pending verification.
    if any(signal.severity == 0 for signal in signals) or (predicted == "HIGH" and benign_context):
        return RiskLevel.LOW
    if predicted == "HIGH":
        return RiskLevel.MEDIUM
    if predicted == "MEDIUM" and not benign_context:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _actions(risk: RiskLevel, signals: list[Signal]) -> list[str]:
    actions: list[str] = []
    categories = {signal.category for signal in signals}
    if risk == RiskLevel.HIGH:
        actions.append("Pause the conversation. Do not send money, identity documents, bank details, passwords, or one-time codes.")
    if "Identity document request" in categories:
        actions.append("Verify the job and recruiter independently; share identity documents only through a confirmed employer onboarding process.")
    if "Financial information request" in categories or "Recruitment fee or deposit" in categories:
        actions.append("Do not pay a recruitment fee or disclose financial details. Contact the employer using its official website's contact information.")
    if "Candidate-paid recruitment expense" in categories:
        actions.append("Do not buy equipment, training, vouchers, certificates, or pay deposits/administrative charges to secure a job. Verify any required expense with the employer through an independently found channel.")
    if "Unclear recruitment expense" in categories:
        actions.append("Ask whether any cost is payable by you and get the written policy from the employer through an independently verified channel before proceeding.")
    if "Password or one-time code request" in categories:
        actions.append("Never share a password or one-time code. If you already shared one, change the password and secure the affected account now.")
    if categories & {"Artificial urgency", "Offer cancellation pressure", "Secrecy or blocked verification", "Unusual selection claim"}:
        actions.append("Take time to verify the role through the employer's independently located careers page or HR contact.")
    if not actions:
        actions.append("No strong warning signal was identified. This does not prove the opportunity is safe; verify the recruiter independently.")
    actions.append("Do not provide passwords, OTPs, or full identity document numbers in this chat or to an unverified recruiter.")
    return list(dict.fromkeys(actions))


def _fallback(message: str, signals: list[Signal]) -> MessageAnalysisResponse:
    risk = _risk_from_hybrid("LOW", signals, is_benign_recruitment_context(message))
    findings = [_quote_finding(signal) for signal in signals]
    return MessageAnalysisResponse(
        risk_level=risk,
        findings=findings,
        recommended_actions=_actions(risk, signals),
        disclaimer=FALLBACK_DISCLAIMER,
        analysis_type="baseline_fallback",
    )


def analyze_message(message: str, model_path: Path | None = None) -> MessageAnalysisResponse:
    signals = detect_signals(message)
    model = _load_model(str(model_path or default_model_path()))
    if model is None:
        return _fallback(message, signals)

    try:
        predicted = str(model.predict([message])[0])
    except Exception:
        return _fallback(message, signals)
    if predicted not in {"LOW", "MEDIUM", "HIGH"}:
        return _fallback(message, signals)

    risk = _risk_from_hybrid(predicted, signals, is_benign_recruitment_context(message))
    findings = [_quote_finding(signal) for signal in signals]
    if predicted != "LOW" and not findings and risk != RiskLevel.LOW:
        # The model may catch a paraphrase beyond the explicit rule patterns.
        findings.append(Finding(
            category="Overall message pattern",
            explanation=f"The learned text classifier matched wording patterns associated with {predicted.lower()}-risk synthetic recruitment examples. Review the request carefully; this is not proof of fraud.",
            evidence="A wording pattern matched; review the submitted message in your browser.",
        ))
    return MessageAnalysisResponse(
        risk_level=risk,
        findings=findings,
        recommended_actions=_actions(risk, signals),
        disclaimer=DISCLAIMER,
        analysis_type="ai_hybrid",
    )
