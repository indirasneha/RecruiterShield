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
    """Recognize explicit routine context, not a lone benign keyword anywhere."""
    if has_secure_post_offer_context(message):
        return True
    protective = bool(re.search(
        r"\b(?:we|our recruiters?|the company)\s+(?:never|do not|don't|will not|won't)\s+(?:ask|request|collect)\b"
        r"|\bno (?:application|recruitment|candidate) fee\b|\bno payment is required\b|"
        r"\bnever share (?:an? )?(?:otp|password|one[- ]time code)\b",
        message, re.I,
    ))
    risky_terms = re.search(
        r"\b(?:aadhaar|aadhar|pan(?: card)?|passport|identity document|government id|tax (?:id|card)|"
        r"bank account|routing number|otp|one[- ]time code|password|recovery code|fee|deposit|bond|"
        r"payment|charge|remittance|invoice|reimburse|purchase|voucher|security suite|"
        r"cancel(?:led|ed)?|withdrawn|keep (?:this|the) (?:secret|private)|do not contact)\b",
        message, re.I,
    )
    if risky_terms and not protective:
        return False
    return bool(
        protective
        or re.search(r"\b(?:confirm|choose|reschedule|move|book)\b[^.!?\n]{0,90}\b(?:interview|meeting|calendar|room|time slot)\b", message, re.I)
        or re.search(r"\b(?:resume|cv|curriculum vitae|portfolio)\b", message, re.I)
        or re.search(r"\bapplications? close\b|\bposted (?:closing )?deadline\b|\bdate listed on (?:the )?(?:official )?careers page\b", message, re.I)
        or re.search(r"\bselected\b[^.!?\n]{0,60}\bafter\s+(?:\w+\s+)?interviews?\b", message, re.I)
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
    pronoun_negation = re.search(
        rf"\b(?:{sensitive_terms})\b[^.!?\n]{{0,100}}\b(?:does|do|did) not need\s+(?:them|it|those|these)\b",
        sentence, re.I,
    )
    return bool(negative_before or negative_after or no_details or pronoun_negation)


def _educational_or_warning_context(sentence: str) -> bool:
    """Avoid treating quoted anti-scam advice or awareness examples as a live request."""
    return bool(re.search(
        r"\b(?:scam(?:mer)?s?|fraud(?:ulent)?|phishing|anti[- ]fraud|awareness|warning|educational example)\b"
        r"[^.!?\n]{0,100}\b(?:ask|asks|asked|request|requests|pay|purchase|share|send|transfer|demand)\b|"
        r"\b(?:example|warning|training material)\b[^.!?\n]{0,100}\b(?:candidate|applicant|recruiter)\b",
        sentence, re.I,
    ))


def _sentences(message: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+|\n+", message) if sentence.strip()]


PAYMENT_ITEMS = (
    r"fee|fees|deposit|bond|charge|payment|remittance|invoice|cost|costs|expense|expenses|amount|"
    r"insurance|courier|shipping|customs|voucher|token|training|bootcamp|course|certification|"
    r"credential|software|security suite|equipment|monitor|workstation|device|prepaid|gift card|"
    r"digital signature|notary|stamping|stamp|lab access|seat hold|administration|activation|"
    r"clearance|background screening|success amount|success fee|appointment letter|"
    r"trainer|exam center|exam centre"
)
RECRUITMENT_CONTEXT = (
    r"candidates?|applicants?|intern(?:ship)?s?|graduate cohort|placement|recruit(?:er|ing|ment)?|"
    r"interviews?|interviewer|shortlists?|offers?|joining|onboarding|hiring|selected|selection|finalists?|payroll|employment|"
    r"workstation|start instructions|appointment letter|your desk|your seat|cohorts?|new hires?|paycheck|payroll|"
    r"assessment|final round|mentor|exam center|exam centre|remote hires?|contract|agency"
)


def _candidate_expense_findings(message: str) -> list[Signal]:
    """Find candidate-paid job conditions, including indirect and reimbursable costs."""
    signals: list[Signal] = []
    item = rf"(?:{PAYMENT_ITEMS})"
    action = r"(?:pay|purchase|buy|order|transfer|send|remit|cover|settle|deposit|clear|bear|reimburse|collect|charge|require|due)"
    job_context = re.compile(rf"\b(?:{RECRUITMENT_CONTEXT})\b", re.I)
    direct_payment = re.compile(
        rf"\b{action}\w*\b[^.!?\n]{{0,120}}\b{item}\b|"
        rf"\b{item}\b[^.!?\n]{{0,120}}\b{action}\w*\b|"
        rf"\b(?:required|mandatory|due|must|need(?:s)? to|condition|before|until|once|unless)\b"
        rf"[^.!?\n]{{0,90}}\b{item}\b[^.!?\n]{{0,90}}\b(?:candidate|applicant|intern|hire|you|your)\b|"
        rf"\b{item}\b[^.!?\n]{{0,90}}\b(?:required|mandatory|due|must|collected|billed|charged|reimburs\w*|refundable|refund)\b",
        re.I,
    )
    unclear_cost = re.compile(
        rf"\b{item}\b[^.!?\n]{{0,80}}\b(?:may apply|might apply|unclear|not clear|not clarified|"
        rf"not sure|unsure|checking who|whether (?:the )?candidate|who covers|who pays)\b|"
        rf"\b(?:unclear|not clear|not clarified|not sure|unsure|checking who|whether (?:the )?candidate|"
        rf"who covers|who pays)\b[^.!?\n]{{0,80}}\b{item}\b",
        re.I,
    )
    refused_payment = re.compile(
        r"\b(?:no|not|never|don't|do not|won't|will not|without)\b[^.!?\n]{0,70}"
        r"\b(?:candidate|applicant|intern|you|anyone)?\s*(?:need|needs|have|has|should|must)?\s*"
        r"(?:pay|purchase|buy|transfer|send|cover|settle|bear|owe|charged|billed|required|fee|payment|deposit)\b|"
        r"\b(?:free of charge|at no cost|employer (?:covers|pays|provides)|company (?:covers|pays|provides))\b",
        re.I,
    )
    for sentence in _sentences(message):
        if not job_context.search(message) or _educational_or_warning_context(sentence):
            continue
        if refused_payment.search(sentence):
            continue
        match = direct_payment.search(sentence)
        if not match:
            # Scams often split the cost and reimbursement promise across
            # neighboring clauses. Recruitment context is required above.
            normalized = re.sub(r"[.!?;,:]+", " ", message)
            has_item = re.search(rf"\b{item}s?\b", normalized, re.I)
            cross_clause_spending_action = r"(?:pay|purchase|buy|order|transfer|remit|cover|settle|deposit|clear|bear|reimburse|collect|charge)"
            has_action = re.search(rf"\b{cross_clause_spending_action}\w*\b", normalized, re.I)
            match = direct_payment.search(normalized) or (has_item and has_action)
            if match and refused_payment.search(message):
                match = None
        if match:
            signals.append(Signal(
                "Candidate-paid recruitment expense", 2,
                "A payment, purchase, deposit, or reimbursable expense is tied to progressing in recruitment. Legitimate employers should not make candidates pay to receive or keep a job offer; verify independently and do not pay first.",
                re.sub(r"\s+", " ", message).strip()[:180],
            ))
        elif unclear_cost.search(sentence):
            signals.append(Signal(
                "Unclear recruitment expense", 1,
                "The message leaves a possible candidate-paid recruitment cost unresolved. Ask the employer through an independently verified channel before agreeing or paying.",
                re.sub(r"\s+", " ", sentence).strip()[:180],
            ))
    # A message-level expense pattern may be reached from more than one
    # sentence in the loop; expose one finding per category/evidence pair.
    unique: list[Signal] = []
    seen: set[tuple[str, str]] = set()
    for signal in signals:
        key = (signal.category, signal.evidence.casefold())
        if key not in seen:
            unique.append(signal)
            seen.add(key)
    return unique


def detect_signals(message: str) -> list[Signal]:
    """Find request/context patterns, not mere mentions of sensitive terms."""
    signals: list[Signal] = []
    refusal_pattern = re.compile(r"\b(?:no|without|waive[ds]?)\s+(?:any\s+)?(?:application|registration|processing|training|security\s+deposit|upfront)?\s*(?:fee|payment|deposit)\b", re.IGNORECASE)

    identity_terms = (
        r"aadhaar|aadhar|pan(?:\s+card)?|passport|national\s+id(?:entity)?|identity\s+(?:document|card)|"
        r"government\s+id|(?:driver'?s?\s+)?licen[cs]e(?:\s+(?:number|image|scan|copy))?|tax\s+(?:id|identification)(?:\s+number)?|tax\s+card|"
        r"social\s+security(?:\s+number)?|ssn|id\s+(?:number|image|scan|copy)|proof\s+of\s+identity"
    )
    identity_pattern = (
        rf"\b(?:send|share|provide|upload|submit|attach|email|text|reply with|fill in|enter|"
        rf"need(?:s|ed)?|require(?:s|d)?|request(?:s|ed)?|ask(?:s|ed)? for|demand(?:s|ed)?|collect(?:s|ed)?|"
        rf"forward|verify|confirm|message(?:d)?|cannot proceed without|cannot continue without|cannot finalize without)\b[^.!?\n]{{0,120}}\b(?:{identity_terms})\b"
        rf"|\b(?:{identity_terms})\b[^.!?\n]{{0,120}}\b(?:send|share|provide|upload|submit|attach|email|text|"
        rf"reply with|fill in|enter|need(?:s|ed)?|require(?:s|d)?|request(?:s|ed)?|ask(?:s|ed)? for|demand(?:s|ed)?|"
        rf"collect(?:s|ed)?|forward|verify|confirm)\b"
    )
    identity = _capture(message, identity_pattern)
    if identity:
        sentence = _sentence_for(message, identity)
        if not _educational_or_warning_context(sentence) and not _negates_sensitive_request(sentence, identity_terms):
            if _request_is_in_safe_stage(message, identity):
                signals.append(Signal("Identity document request", 0,
                    "This request is described as post-offer and through a secure employer portal. Confirm the portal independently before uploading anything.", identity))
            else:
                signals.append(Signal("Identity document request", 2,
                    "A recruiter is asking for a government identity document or number. Verify the employer independently and share identity documents only through a confirmed, secure onboarding process.", identity))

    finance_pattern = (
        r"\b(?:send|share|provide|upload|submit|reply with|email|text|enter|confirm|need(?:s|ed)?|require(?:s|d)?|"
        r"request(?:s|ed)?|ask(?:s|ed)? for|collect(?:s|ed)?|forward|cannot proceed without|cannot continue without)\b"
        r"[^.!?\n]{0,120}\b(?:bank\s+(?:account|details|statement|information|routing details)|account\s+number|"
        r"routing\s+(?:number|details|information)|ifsc(?:\s+code)?|debit\s+card|credit\s+card|payment\s+card|"
        r"upi\s+id|wallet\s+details|void\s+cheque|void\s+check|financial\s+(?:details|information))\b"
        r"|\b(?:bank\s+(?:account|details|statement|information|routing details)|account\s+number|routing\s+(?:number|details|information)|"
        r"ifsc(?:\s+code)?|debit\s+card|credit\s+card|payment\s+card|upi\s+id|wallet\s+details|void\s+cheque|void\s+check|"
        r"financial\s+(?:details|information))\b[^.!?\n]{0,120}\b(?:send|share|provide|upload|submit|reply with|email|text|enter|"
        r"confirm|required|need(?:s|ed)?|require(?:s|d)?|ask(?:s|ed)? for|collect(?:s|ed)?|forward)\b"
    )
    financial = _capture(message, finance_pattern)
    if financial:
        sentence = _sentence_for(message, financial)
        financial_terms = r"bank\s+(?:account|details|statement|information|routing details)|account\s+number|routing\s+(?:number|details|information)|ifsc(?:\s+code)?|debit\s+card|credit\s+card|payment\s+card|upi\s+id|wallet\s+details|void\s+(?:cheque|check)|financial\s+(?:details|information)"
        if not _educational_or_warning_context(sentence) and not _negates_sensitive_request(sentence, financial_terms):
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
    if fee and not _educational_or_warning_context(fee_sentence) and not refusal_pattern.search(fee_sentence) and not re.search(r"\b(?:never|do not|don't|not)\s+(?:pay|send|transfer)\b", fee_sentence, re.I):
        signals.append(Signal("Recruitment fee or deposit", 2,
            "Legitimate employers generally do not require candidates to pay to apply, interview, or receive an offer.", fee))

    credential_pattern = (
        r"\b(?:send|share|provide|tell|text|reply with|read(?: back)?|repeat|forward|relay|enter|confirm|give us|"
        r"need(?:s|ed)?|require(?:s|d)?|request(?:s|ed)?|ask(?:s|ed)? for)\b"
        r"[^.!?\n]{0,100}\b(?:otp|one[- ]time\s+(?:password|passcode|code)|verification\s+code|login\s+code|"
        r"sign[- ]in\s+code|authenticator\s+(?:app|code|number)|authentication\s+code|password|passphrase|"
        r"account\s+credentials|recovery\s+code)\b"
        r"|\b(?:otp|one[- ]time\s+(?:password|passcode|code)|verification\s+code|login\s+code|sign[- ]in\s+code|"
        r"authenticator\s+(?:app|code|number)|authentication\s+code|password|passphrase|account\s+credentials|recovery\s+code)\b"
        r"[^.!?\n]{0,100}\b(?:send|share|provide|tell|text|reply with|read(?: back)?|repeat|forward|relay|enter|confirm|required|"
        r"need(?:s|ed)?|require(?:s|d)?|request(?:s|ed)?|ask(?:s|ed)? for)\b"
    )
    credential = _capture(message, credential_pattern)
    # A direction to read back numeric digits is credential disclosure when
    # the same message ties the digits to a login, verification, or authenticator code.
    if not credential:
        digit_request = _capture(message, r"\b(?:read|repeat|send|share|reply with|forward)\b[^.!?\n]{0,50}\b(?:the\s+)?(?:four|six|eight|\d{4,8})\s+digits\b")
        if digit_request and re.search(r"\b(?:login|sign[- ]in|verification|authenticator|one[- ]time)\b", message, re.I):
            credential = digit_request
    if credential:
        sentence = _sentence_for(message, credential)
        credential_terms = r"otp|one[- ]time\s+(?:password|passcode|code)|verification\s+code|login\s+code|sign[- ]in\s+code|authenticator\s+(?:app|code|number)|authentication\s+code|password|passphrase|account\s+credentials|recovery\s+code"
    else:
        sentence = ""
        credential_terms = r""
    if credential and not _educational_or_warning_context(sentence) and not _negates_sensitive_request(sentence, credential_terms):
        signals.append(Signal("Password or one-time code request", 2,
            "A legitimate recruiter should never need your password or one-time sign-in code; sharing it can hand over an account.", credential))

    signals.extend(_candidate_expense_findings(message))

    urgency = _capture(message,
        r"\b(?:within\s+(?:\d+|one|two|three|an?)\s*(?:minutes?|hours?|days?)|"
        r"in\s+the\s+next\s+\d+\s*(?:minutes?|hours?)|immediately|right now|today only|tonight only|through tonight|act now|"
        r"urgent(?:ly)?|countdown|timer expires|before (?:midnight|noon|this evening|close of business|\d{1,2}\s*(?:am|pm))|"
        r"today|expires? (?:tonight|today|in \d+\s*(?:minutes?|hours?))|"
        r"by (?:tonight|midnight|noon|this evening|close of business|\d{1,2}\s*(?:am|pm))|last chance)\b")
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
        r"\b(?:do not|don't|never|please do not)\s+(?:contact|call|email|tell|inform|discuss|share|speak to|ask)\b"
        r"[^.!?\n]{0,50}\b(?:company|hr|human resources|anyone|others|manager|office|employer|recruiting team)\b"
        r"|\b(?:discourage|discourages|discouraged|avoid|avoid contacting)\b[^.!?\n]{0,45}"
        r"\b(?:call|contact|email|speak to)\b[^.!?\n]{0,30}\b(?:company|hr|employer|recruiting team)\b"
        r"|\bkeep\s+(?:this|the)\s+(?:private|confidential|secret|between us|between ourselves|(?:opening|role|offer|selection|conversation|message)\s+(?:private|confidential|secret))\b[^.!?\n]{0,50}"
        r"\b(?:company|hr|human resources|anyone|others|manager|office|employer|careers team|until)\b|"
        r"\b(?:private mailbox|personal mailbox|private number|personal number|reply with a photo|send a photo)\b|"
        r"\bdo not ask (?:the )?(?:careers|recruiting|hr) team\b|"
        r"\bkeep\s+(?:the )?(?:search|application|request)\s+off\s+(?:your )?(?:public )?(?:application )?record\b")
    if secrecy:
        signals.append(Signal("Secrecy or blocked verification", 1,
            "Discouraging contact with the company prevents you from checking whether the recruiter and offer are genuine.", secrecy))

    selection = _capture(message,
        r"\bthere will be no (?:usual|formal|further) interview\b|"
        r"\b(?:selected|hired|chosen|offer(?:ed)? the (?:job|role|position))\b[^.!?\n]{0,80}\b"
        r"(?:without (?:an? )?(?:interview|assessment)|no (?:usual|formal|further )?interview|there will be no (?:usual|formal )?interview|before (?:any )?interview|"
        r"guaranteed|immediately|instantly|without evaluation)\b"
        r"|\b(?:no (?:usual|formal|further )?interview|without (?:an? )?interview|guaranteed selection|instant selection|"
        r"selected without (?:an? )?assessment)\b")
    if selection:
        signals.append(Signal("Unusual selection claim", 1,
            "An unconditional selection claim without a normal interview or assessment deserves independent confirmation.", selection))

    return signals
