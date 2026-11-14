"""Regression tests for Phase 6B red-team misses and safe counterexamples."""

import csv
from pathlib import Path

import pytest

from app.services.analyzer import analyze_message
from app.services.signals import detect_signals


ROOT = Path(__file__).resolve().parents[1]
REDTEAM = ROOT / "data" / "redteam" / "messages.csv"


def _redteam_high_messages() -> list[tuple[str, str]]:
    with REDTEAM.open(newline="", encoding="utf-8") as stream:
        return [
            (row["id"], row["text"])
            for row in csv.DictReader(stream)
            if row["true_label"] == "HIGH"
        ]


@pytest.mark.parametrize(("case_id", "message"), _redteam_high_messages())
def test_every_high_redteam_case_stays_high(case_id: str, message: str):
    """Protect each previously missed fraud case without training on the corpus."""
    result = analyze_message(message)
    assert result.risk_level.value == "HIGH", case_id
    assert result.findings, case_id


@pytest.mark.parametrize("message", [
    "We never ask candidates to share an OTP or password, and there is no application fee.",
    "Please send your resume and portfolio link so we can review your application.",
    "Would Tuesday or Thursday suit you for a video interview with the hiring team?",
    "Please confirm today's interview by 4 pm so the room can be reserved.",
    "After accepting the written offer, upload your passport using the secure employee portal.",
    "The official payroll tool requests bank details after contract acceptance.",
    "The company provides a laptop at no cost; candidates should not buy equipment.",
    "Our careers page says there is no registration fee and applicants should never transfer money.",
    "Security awareness example: scammers may ask for a refundable deposit; never pay it.",
    "The panel selected you after two interviews and a practical assessment. We will send a written offer for review.",
    "The onboarding checklist mentions PAN and bank details for later payroll setup; the recruiter does not need them now.",
])
def test_legitimate_or_protective_counterexamples_are_not_high(message: str):
    assert analyze_message(message).risk_level.value != "HIGH"


@pytest.mark.parametrize(("message", "category"), [
    ("For this internship, buy the required training voucher today; we will reimburse it after your first week.", "Candidate-paid recruitment expense"),
    ("Pay a refundable seat-hold deposit before the agency issues your appointment letter.", "Candidate-paid recruitment expense"),
    ("Order the designated monitor and we will add its cost to your first paycheck after you join.", "Candidate-paid recruitment expense"),
    ("A background partner requires a refundable screening remittance from every remote hire.", "Candidate-paid recruitment expense"),
    ("The agency charges a success administration amount; pay its invoice before contract processing.", "Candidate-paid recruitment expense"),
    ("Text your Aadhaar number to this account and do not ask the careers team about the exception.", "Secrecy or blocked verification"),
    ("Keep this between us and message your PAN scan to my private number.", "Secrecy or blocked verification"),
])
def test_indirect_patterns_have_specific_explainable_findings(message: str, category: str):
    result = analyze_message(message)
    assert result.risk_level.value == "HIGH"
    assert category in {finding.category for finding in result.findings}


def test_separate_low_context_does_not_cancel_credential_request():
    message = "The interview is on Friday. Read back the six digits from your authenticator app to activate the candidate account."
    result = analyze_message(message)
    assert result.risk_level.value == "HIGH"
    assert "Password or one-time code request" in {finding.category for finding in result.findings}


def test_fee_warning_is_not_a_candidate_payment_signal():
    message = "Candidates never pay an administration charge; report any recruiter who requests one."
    assert "Candidate-paid recruitment expense" not in {signal.category for signal in detect_signals(message)}

