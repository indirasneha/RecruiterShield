"""Evidence-bearing context signals for recruitment identity-harvesting messages."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    category: str
    severity: int  # 1 = caution, 2 = dangerous request
    explanation: str
    evidence: str


def _capture(message: str, pattern: str, flags: int = re.IGNORECASE) -> str | None:
    match = re.search(pattern, message, flags)
    if not match:
        return None
    # Keep evidence short and exact, so the result can be checked against the input.
    return re.sub(r"\s+", " ", match.group(0)).strip()[:180]


def _sentence_for(message: str, evidence: str) -> str:
    # Apply negation to the sentence containing a signal, never to the whole
    # message: a reassuring sentence must not cancel a separate dangerous ask.
    return next((sentence for sentence in re.split(r"(?<=[.!?])\s+|\n+", message)
                 if evidence.casefold() in sentence.casefold()), message)


def has_secure_post_offer_context(message: str) -> bool:
    stage = re.search(
        r"\b(?:after|following|once)\b[^.!?\n]{0,90}\b(?:accept(?:ed|ing|ance)?|sign(?:ed|ing)?)\b"
        r"[^.!?\n]{0,50}\b(?:offer|contract|onboarding|employment)\b|"
        r"\b(?:once|after)\b[^.!?\n]{0,45}\b(?:offer|contract)\b[^.!?\n]{0,25}\b(?:signed|accepted)\b|"
        r"\bafter\s+(?:the\s+)?(?:written\s+)?(?:offer|contract)\s+(?:is\s+)?(?:signed|accepted)\b|"
        r"\bafter\s+(?:contract\s+)?acceptance\b|\bpost[- ]offer\b|\bafter onboarding\b",
        message, re.IGNORECASE,
    )
    channel = re.search(
        r"\b(?:secure|official|approved|employer's|company's|company|employer)\b[^.!?\n]{0,50}"
        r"\b(?:portal|payroll system|payroll tool|hr system|employee portal|onboarding portal)\b|"
        r"\b(?:portal|payroll system|payroll tool|hr system|employee portal|onboarding portal)\b"
        r"[^.!?\n]{0,50}\b(?:secure|official|approved)\b",
        message, re.IGNORECASE,
    )
    return bool(stage and channel)


def _request_is_in_safe_stage(message: str, evidence: str) -> bool:
    sentence = _sentence_for(message, evidence)
    if not has_secure_post_offer_context(sentence):
        return False
    # Do not let a broad reassurance elsewhere in the message legitimize an
    # explicitly early, private, or unverified request in this same passage.
    conflicts = re.search(
        r"\b(?:before (?:the )?(?:first )?interview|before (?:an? )?offer|private chat|"
        r"unverified|unknown form|unofficial form|immediately|right now|today only|act now)\b",
        sentence, re.I,
    )
    return not conflicts


def is_benign_recruitment_context(message: str) -> bool:
    """Recognize ordinary process language when no active danger signal exists."""
    return bool(
        has_secure_post_offer_context(message)
        or re.search(r"\b(?:resume|cv|curriculum vitae|portfolio)\b", message, re.I)
        or re.search(r"\b(?:schedule|reschedule|calendar|interview|meeting|room booking|time slot|appointment|available)\b", message, re.I)
        or re.search(r"\bapplications? close\b|\bposted (?:closing )?deadline\b|\bdate listed on (?:the )?(?:official )?careers page\b", message, re.I)
        or re.search(r"\bselected\b[^.!?\n]{0,60}\bafter\s+(?:\w+\s+)?interviews?\b", message, re.I)
        or re.search(r"\b(?:never ask|do not ask|don't ask|do not request|don't request|no application fee|no recruitment fee|not required for the application)\b", message, re.I)
    )


def _negates_sensitive_request(sentence: str, sensitive_terms: str) -> bool:
    negative_before = re.search(
        rf"\b(?:no|not|never|don't|do not|won't|will not)\b[^.!?\n]{{0,45}}"
        rf"\b(?:need|needed|required|request|ask|collect|send|share|provide|upload|submit|email)\b"
        rf"[^.!?\n]{{0,45}}\b(?:{sensitive_terms})\b", sentence, re.I,
    )
    negative_after = re.search(
        rf"\b(?:{sensitive_terms})\b[^.!?\n]{{0,30}}\b(?:is|are|was|were)?\s*"
        r"(?:not required|not needed|not requested|not collected|isn't required|isn't needed)\b",
        sentence, re.I,
    )
    no_details = re.search(
        rf"\bno\s+(?:{sensitive_terms})\b[^.!?\n]{{0,20}}\b(?:needed|required|requested|collected)\b",
        sentence, re.I,
    )
    return bool(negative_before or negative_after or no_details)


def detect_signals(message: str) -> list[Signal]:
    """Find request/context patterns, not mere mentions of sensitive terms."""
    signals: list[Signal] = []

    # Explicit anti-scam warnings and denials should not be misread as requests.
    protective_pattern = re.compile(
        r"\b(?:never|do not|don't|won't|will not|not required|no need to|we never ask)\b.{0,90}"
        r"\b(?:send|share|provide|pay|upload|submit|request|ask for|need)\b",
        re.IGNORECASE,
    )
    refusal_pattern = re.compile(r"\b(?:no|without|waive[ds]?)\s+(?:any\s+)?(?:application|registration|processing|training|security\s+deposit|upfront)?\s*(?:fee|payment|deposit)\b", re.IGNORECASE)

    identity_pattern = (
        r"\b(?:send|share|provide|upload|submit|attach|email|text|reply with|fill in|enter|"
        r"we need|we require|please provide|must provide|requested|requests?|ask for|asks for|asked for|demand)\b[^.!?\n]{0,100}\b"
        r"(?:aadhaar|aadhar|pan(?:\s+card)?|passport|national\s+id(?:entity)?|identity\s+(?:document|card)|"
        r"government\s+id|driver'?s?\s+licen[cs]e|tax\s+id|social\s+security(?:\s+number)?|ssn)\b"
        r"|\b(?:aadhaar|aadhar|pan(?:\s+card)?|passport|national\s+id(?:entity)?|identity\s+(?:document|card)|"
        r"government\s+id|driver'?s?\s+licen[cs]e|tax\s+id|social\s+security(?:\s+number)?|ssn)\b"
        r"[^.!?\n]{0,100}\b(?:send|share|provide|upload|submit|attach|email|text|reply with|fill in|enter|required|"
        r"need|needed|require|requested|request|ask for|asked for)\b"
    )
    identity = _capture(message, identity_pattern)
    if identity:
        sentence = _sentence_for(message, identity)
        identity_terms = r"aadhaar|aadhar|pan(?:\s+card)?|passport|national\s+id(?:entity)?|identity\s+(?:document|card)|government\s+id|driver'?s?\s+licen[cs]e|tax\s+id|social\s+security(?:\s+number)?|ssn"
        if not protective_pattern.search(sentence) and not _negates_sensitive_request(sentence, identity_terms):
            if _request_is_in_safe_stage(message, identity):
                signals.append(Signal("Identity document request", 0,
                    "This request is described as post-offer and through a secure employer portal. Confirm the portal independently before uploading anything.", identity))
            else:
                signals.append(Signal("Identity document request", 2,
                    "A recruiter is asking for a government identity document or number. Verify the employer independently and share identity documents only through a confirmed, secure onboarding process.", identity))

    finance_pattern = (
        r"\b(?:send|share|provide|upload|submit|reply with|enter|confirm|we need|we require|please provide)\b"
        r"[^.!?\n]{0,90}\b(?:bank\s+(?:account|details|statement|information)|account\s+number|"
        r"routing\s+number|ifsc(?:\s+code)?|debit\s+card|credit\s+card|upi\s+id|wallet\s+details|"
        r"financial\s+(?:details|information))\b"
        r"|\b(?:bank\s+(?:account|details|statement|information)|account\s+number|routing\s+number|ifsc(?:\s+code)?|"
        r"debit\s+card|credit\s+card|upi\s+id|wallet\s+details|financial\s+(?:details|information))\b"
        r"[^.!?\n]{0,90}\b(?:send|share|provide|upload|submit|reply with|enter|confirm|required|need|needed|require)\b"
    )
    financial = _capture(message, finance_pattern)
    if financial:
        sentence = _sentence_for(message, financial)
        financial_terms = r"bank\s+(?:account|details|statement|information)|account\s+number|routing\s+number|ifsc(?:\s+code)?|debit\s+card|credit\s+card|upi\s+id|wallet\s+details|financial\s+(?:details|information)"
        if not protective_pattern.search(sentence) and not _negates_sensitive_request(sentence, financial_terms):
            if _request_is_in_safe_stage(message, financial):
                signals.append(Signal("Financial information request", 0,
                    "This request is described as post-offer payroll setup in a secure employer system. Verify the system independently before entering information.", financial))
            else:
                signals.append(Signal("Financial information request", 2,
                    "Sharing bank or payment details with an unverified recruiter can expose funds and enable identity misuse.", financial))

    fee_pattern = (
        r"\b(?:pay|transfer|send|deposit|wire|submit|cover|reimburse|purchase)\b[^.!?\n]{0,100}\b"
        r"(?:registration|processing|training|security|verification|interview|placement|onboarding)?\s*"
        r"(?:fee|fees|deposit|charge|payment|money)\b"
        r"|\b(?:registration|processing|training|security|verification|interview|placement|onboarding)\s+"
        r"(?:fee|fees|deposit|charge|payment)\b[^.!?\n]{0,100}\b(?:due|required|mandatory|pay|transfer|send|deposit|"
        r"before|to secure|to release|to continue)\b"
    )
    fee = _capture(message, fee_pattern)
    fee_sentence = _sentence_for(message, fee or "")
    if fee and not refusal_pattern.search(fee_sentence) and not re.search(r"\b(?:never|do not|don't|not)\s+(?:pay|send|transfer)\b", fee_sentence, re.I):
        signals.append(Signal("Recruitment fee or deposit", 2,
            "Legitimate employers generally do not require candidates to pay to apply, interview, or receive an offer.", fee))

    credential_pattern = (
        r"\b(?:send|share|provide|tell|text|reply with|enter|confirm|give us|we need|we require|please provide)\b"
        r"[^.!?\n]{0,80}\b(?:otp|one[- ]time\s+(?:password|passcode|code)|verification\s+code|login\s+code|"
        r"password|passphrase|account\s+credentials|recovery\s+code)\b"
        r"|\b(?:otp|one[- ]time\s+(?:password|passcode|code)|verification\s+code|login\s+code|password|"
        r"passphrase|account\s+credentials|recovery\s+code)\b[^.!?\n]{0,80}\b(?:send|share|provide|tell|text|"
        r"reply with|enter|confirm|required|need|needed)\b"
    )
    credential = _capture(message, credential_pattern)
    if credential and not protective_pattern.search(_sentence_for(message, credential)):
        signals.append(Signal("Password or one-time code request", 2,
            "A legitimate recruiter should never need your password or one-time sign-in code; sharing it can hand over an account.", credential))

    urgency = _capture(message,
        r"\b(?:within\s+(?:\d+|one|two|three|an?)\s*(?:minutes?|hours?|days?)|"
        r"in\s+the\s+next\s+\d+\s*(?:minutes?|hours?)|immediately|right now|today only|act now|"
        r"urgent(?:ly)?|before (?:midnight|noon|this evening|\d{1,2}\s*(?:am|pm))|"
        r"today|expires? (?:tonight|today|in \d+\s*(?:minutes?|hours?))|"
        r"by (?:tonight|midnight|noon|this evening)|last chance)\b")
    routine_schedule = bool(re.search(r"\b(?:interview|meeting|calendar|room booking|attendance|time slot|appointment)\b", message, re.I))
    pressure_context = bool(re.search(
        r"\b(?:unless|cancel(?:led|ed)?|withdraw|revok|lose your place|no interview|without (?:an? )?interview|"
        r"do not contact|don't contact|keep (?:this|the) (?:secret|private)|identity|passport|aadhaar|aadhar|pan|"
        r"bank|deposit|fee|payment|otp|password|employer details later|company details later)\b", message, re.I
    ))
    if urgency and (pressure_context or not routine_schedule):
        signals.append(Signal("Artificial urgency", 1,
            "Pressure to act unusually quickly can prevent independent checks. A normal application deadline alone is not proof of fraud.", urgency))

    cancellation = _capture(message,
        r"\b(?:your|the)\s+(?:job\s+)?offer\s+(?:will be|is|may be)?\s*(?:cancelled|canceled|withdrawn|revoked|forfeited)\b"
        r"[^.!?\n]{0,70}\b(?:unless|if you (?:do not|don't|fail)|or else|or (?:your|the) offer)\b"
        r"|\b(?:unless|if you (?:do not|don't|fail))\b[^.!?\n]{0,70}"
        r"\b(?:lose|forfeit|cancel|withdraw)\s+(?:your|the)\s+(?:job\s+)?offer\b"
        r"|\bor\s+(?:your|the)\s+(?:job\s+)?offer\s+(?:will be|is|may be)?\s*(?:cancelled|canceled|withdrawn|revoked|forfeited)\b")
    if cancellation:
        signals.append(Signal("Offer cancellation pressure", 1,
            "Threatening to withdraw an offer unless you comply can be coercive, especially when paired with requests for money or identity data.", cancellation))

    secrecy = _capture(message,
        r"\b(?:do not|don't|never|please do not)\s+(?:contact|call|email|tell|inform|discuss|share|speak to)\b"
        r"[^.!?\n]{0,50}\b(?:company|hr|human resources|anyone|others|manager|office|employer|recruiting team)\b"
        r"|\b(?:discourage|discourages|discouraged|avoid|avoid contacting)\b[^.!?\n]{0,45}"
        r"\b(?:call|contact|email|speak to)\b[^.!?\n]{0,30}\b(?:company|hr|employer|recruiting team)\b"
        r"|\bkeep\s+(?:this|the)\s+(?:private|confidential|secret|(?:opening|role|offer|selection|conversation|message)\s+(?:private|confidential|secret))\b[^.!?\n]{0,50}"
        r"\b(?:company|hr|human resources|anyone|others|manager|office|employer)\b")
    if secrecy:
        signals.append(Signal("Secrecy or blocked verification", 1,
            "Discouraging contact with the company prevents you from checking whether the recruiter and offer are genuine.", secrecy))

    selection = _capture(message,
        r"\b(?:selected|hired|chosen|offer(?:ed)? the (?:job|role|position))\b[^.!?\n]{0,80}\b"
        r"(?:without (?:an? )?(?:interview|assessment)|no interview|before (?:any )?interview|"
        r"guaranteed|immediately|instantly|without evaluation)\b"
        r"|\b(?:no interview|without (?:an? )?interview|guaranteed selection|instant selection|"
        r"selected without (?:an? )?assessment)\b")
    if selection:
        signals.append(Signal("Unusual selection claim", 1,
            "An unconditional selection claim without a normal interview or assessment deserves independent confirmation.", selection))

    return signals
