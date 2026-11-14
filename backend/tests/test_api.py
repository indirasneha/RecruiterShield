from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_valid_message_analysis():
    response = client.post("/api/analyze/message", json={"text": "Pay a processing fee today to secure your internship."})
    assert response.status_code == 200
    payload = response.json()
    assert payload["risk_level"] == "HIGH"
    assert payload["findings"]
    assert payload["findings"][0]["evidence"]
    assert payload["recommended_actions"]
    assert "does not independently verify" in payload["disclaimer"]
    assert payload["analysis_type"] == "ai_hybrid"


def test_legitimate_resume_and_interview_are_not_high_risk():
    examples = [
        "Please send your resume and portfolio link so we can review your application.",
        "Would Tuesday or Thursday suit you for a video interview with the hiring team?",
        "Your application is under review. We will contact shortlisted candidates after the posted deadline.",
    ]
    for text in examples:
        response = client.post("/api/analyze/message", json={"text": text})
        assert response.status_code == 200
        assert response.json()["risk_level"] != "HIGH", text


def test_identity_harvesting_attacks_are_high_risk_with_evidence():
    attacks = [
        "Send your Aadhaar card today or your offer will be canceled.",
        "Pay a processing fee now to secure your internship.",
        "Reply with the OTP from your phone to verify your candidate account.",
        "Provide your bank account details before the interview to release your stipend.",
    ]
    for text in attacks:
        response = client.post("/api/analyze/message", json={"text": text})
        payload = response.json()
        assert response.status_code == 200
        assert payload["risk_level"] == "HIGH", text
        assert payload["findings"], text
        assert any(finding["evidence"].strip("“”") in text for finding in payload["findings"]), text
        assert payload["analysis_type"] == "ai_hybrid"


def test_protective_warning_is_not_misread_as_a_request():
    response = client.post("/api/analyze/message", json={
        "text": "We never ask candidates to share an OTP or password, and there is no application fee."
    })
    assert response.status_code == 200
    assert response.json()["risk_level"] == "LOW"
    assert response.json()["findings"] == []


def test_safety_language_does_not_cancel_a_separate_identity_request():
    response = client.post("/api/analyze/message", json={
        "text": "We never ask candidates to share an OTP. Please send your Aadhaar card before the interview."
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["risk_level"] == "MEDIUM"
    assert any(finding["category"] == "Identity document request" for finding in payload["findings"])


def test_artificial_deadline_is_explained_without_sensitive_request():
    response = client.post("/api/analyze/message", json={
        "text": "Please confirm by this evening whether you remain interested in the role."
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["risk_level"] == "MEDIUM"
    assert any(finding["category"] == "Artificial urgency" for finding in payload["findings"])


def test_secure_post_offer_document_and_payroll_steps_are_not_high_risk():
    examples = [
        "After accepting the written offer, upload your passport using the secure employee portal.",
        "The official payroll tool requests bank details after contract acceptance.",
    ]
    for text in examples:
        payload = client.post("/api/analyze/message", json={"text": text}).json()
        assert payload["risk_level"] == "LOW", text


def test_legitimate_interview_confirmation_deadline_is_not_artificial_urgency():
    text = "Please confirm today's interview by 4 pm so the room can be reserved."
    payload = client.post("/api/analyze/message", json={"text": text}).json()
    assert payload["risk_level"] == "LOW"
    assert not any(finding["category"] == "Artificial urgency" for finding in payload["findings"])


def test_early_pan_request_is_medium_and_supported_by_evidence():
    text = "A recruiter asks for a PAN image before the first interview through an unknown form."
    payload = client.post("/api/analyze/message", json={"text": text}).json()
    assert payload["risk_level"] == "MEDIUM"
    assert any(finding["category"] == "Identity document request" for finding in payload["findings"])


def test_identity_request_combined_with_offer_threat_is_high():
    text = "Upload your Aadhaar now or the offer will be canceled this evening."
    payload = client.post("/api/analyze/message", json={"text": text}).json()
    assert payload["risk_level"] == "HIGH"
    categories = {finding["category"] for finding in payload["findings"]}
    assert {"Identity document request", "Offer cancellation pressure"} <= categories


def test_safety_advice_not_to_email_documents_is_not_secrecy():
    text = "Do not email identity documents to a recruiter; use the secure portal after the signed offer."
    payload = client.post("/api/analyze/message", json={"text": text}).json()
    assert payload["risk_level"] == "LOW"
    assert not any(finding["category"] == "Secrecy or blocked verification" for finding in payload["findings"])


def test_safe_portal_mention_does_not_excuse_separate_early_id_request():
    text = "The official secure portal is ready after acceptance. Before your first interview, send your Aadhaar through this private chat."
    payload = client.post("/api/analyze/message", json={"text": text}).json()
    assert payload["risk_level"] == "MEDIUM"
    assert any(finding["category"] == "Identity document request" for finding in payload["findings"])


def test_nonconditional_offer_timing_is_not_a_cancellation_threat():
    text = "The offer may be withdrawn soon, but no document or payment is requested."
    payload = client.post("/api/analyze/message", json={"text": text}).json()
    assert payload["risk_level"] == "MEDIUM"
    assert not any(finding["category"] == "Offer cancellation pressure" for finding in payload["findings"])


def test_missing_model_has_explicit_fallback_indicator(tmp_path):
    from app.services.analyzer import analyze_message

    result = analyze_message("Please send your Aadhaar card before the interview.", model_path=tmp_path / "missing.joblib")
    assert result.analysis_type == "baseline_fallback"
    assert "trained text model is unavailable" in result.disclaimer
    assert result.risk_level == "MEDIUM"


def test_empty_input_is_rejected():
    assert client.post("/api/analyze/message", json={"text": "  "}).status_code == 422


def test_oversized_input_is_rejected():
    assert client.post("/api/analyze/message", json={"text": "x" * 12_001}).status_code == 422


def test_malformed_requests_are_rejected():
    assert client.post("/api/analyze/message", json={"message": "hello"}).status_code == 422
    assert client.post("/api/analyze/message", content="not-json", headers={"Content-Type": "application/json"}).status_code == 422


def test_validation_errors_never_echo_submitted_message_content():
    secret = "synthetic-private-message-content"
    response = client.post("/api/analyze/message", json={"text": secret, "unexpected": secret})
    assert response.status_code == 422
    assert secret not in response.text


def test_message_request_body_is_bounded_before_json_parsing():
    response = client.post(
        "/api/analyze/message",
        content=b'{"text":"' + b"x" * (64 * 1024) + b'"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_api_responses_disable_storage_and_set_security_headers():
    response = client.post("/api/analyze/message", json={"text": "Please share your Aadhaar before interview."})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_cors_allows_configured_frontend_and_not_arbitrary_sites():
    trusted = client.options("/api/analyze/message", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    untrusted = client.options("/api/analyze/message", headers={
        "Origin": "https://attacker.example",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert trusted.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-origin" not in untrusted.headers


def test_sensitive_identifiers_are_redacted_from_returned_evidence():
    response = client.post("/api/analyze/message", json={
        "text": "Send Aadhaar 1234 5678 9012 and PAN ABCDE1234F before the interview."
    })
    assert response.status_code == 200
    assert "1234 5678 9012" not in response.text
    assert "ABCDE1234F" not in response.text
    assert "[redacted" in response.text


def test_process_local_analysis_throttle_limits_bursts_per_client():
    from app.main import ANALYSIS_RATE_LIMIT, _consume_analysis_request, _request_times

    client_ip = "synthetic-rate-limit-test"
    _request_times.pop(client_ip, None)
    for index in range(ANALYSIS_RATE_LIMIT):
        assert _consume_analysis_request(client_ip, now=100.0 + index / 100) == 0
    retry_after = _consume_analysis_request(client_ip, now=101.0)
    assert retry_after > 0
    assert _consume_analysis_request(client_ip, now=161.0) == 0
    _request_times.pop(client_ip, None)
