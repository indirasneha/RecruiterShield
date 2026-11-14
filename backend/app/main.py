import asyncio
import os
import threading
import time
from collections import deque
from math import ceil

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.api.schemas import MAX_MESSAGE_LENGTH, MessageAnalysisRequest, MessageAnalysisResponse
from app.services.analyzer import analyze_message
from app.services.document_analysis import DocumentAnalysisError, MAX_PDF_BYTES, analyze_pdf

app = FastAPI(title="RecruiterShield API", version="0.2.0", description="Hybrid contextual recruitment identity-harvesting risk assessment.")

origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]
if "*" in origins:
    raise RuntimeError("CORS_ORIGINS must list explicit trusted origins; wildcard CORS is not allowed.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

MAX_MESSAGE_BODY_BYTES = 64 * 1024
ANALYSIS_RATE_LIMIT = 60
ANALYSIS_RATE_WINDOW_SECONDS = 60
MAX_RATE_LIMIT_CLIENTS = 4_096
_request_times: dict[str, deque[float]] = {}
_request_times_lock = threading.Lock()
_rate_limit_checks = 0
_pdf_analysis_slots = asyncio.Semaphore(2)


def _consume_analysis_request(client_ip: str, now: float | None = None) -> int:
    """Return retry seconds when throttled; the in-process limit is a local safeguard."""
    current = time.monotonic() if now is None else now
    window_start = current - ANALYSIS_RATE_WINDOW_SECONDS
    global _rate_limit_checks
    with _request_times_lock:
        _rate_limit_checks += 1
        # Expire inactive client entries periodically so spoofed/changing peers
        # cannot grow this process-local bookkeeping without bound.
        if _rate_limit_checks % 64 == 0:
            expired = [ip for ip, times in _request_times.items() if not times or times[-1] <= window_start]
            for ip in expired:
                _request_times.pop(ip, None)
        if client_ip not in _request_times and len(_request_times) >= MAX_RATE_LIMIT_CLIENTS:
            return ANALYSIS_RATE_WINDOW_SECONDS
        recent = deque(t for t in _request_times.get(client_ip, ()) if t > window_start)
        if len(recent) >= ANALYSIS_RATE_LIMIT:
            _request_times[client_ip] = recent
            return max(1, ceil(recent[0] + ANALYSIS_RATE_WINDOW_SECONDS - current))
        recent.append(current)
        _request_times[client_ip] = recent
        return 0


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "recruitershield-api"}


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    if request.method == "POST" and request.url.path in {"/api/analyze/message", "/api/analyze/document"}:
        client_ip = request.client.host if request.client else "unknown"
        retry_after = _consume_analysis_request(client_ip)
        if retry_after:
            response = JSONResponse(
                status_code=429,
                content={"detail": "Too many analysis requests. Wait before trying again."},
                headers={"Retry-After": str(retry_after)},
            )
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Cache-Control"] = "no-store"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            return response
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.post("/api/analyze/message", response_model=MessageAnalysisResponse, response_model_exclude_none=True)
async def analyze(request: Request) -> MessageAnalysisResponse | JSONResponse:
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_MESSAGE_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "The request exceeds the message analysis size limit."})

    body = bytearray()
    try:
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_MESSAGE_BODY_BYTES:
                return JSONResponse(status_code=413, content={"detail": "The request exceeds the message analysis size limit."})
            body.extend(chunk)
        try:
            payload = MessageAnalysisRequest.model_validate_json(bytes(body))
        except ValidationError as exc:
            # Pydantic's default errors include the submitted input. Return only
            # structural validation details so sensitive message text is not echoed.
            safe_errors = [
                {"loc": error.get("loc", ()), "msg": error.get("msg", "Invalid request."), "type": error.get("type", "value_error")}
                for error in exc.errors()
            ]
            return JSONResponse(status_code=422, content={"detail": safe_errors})
        if len(payload.text) > MAX_MESSAGE_LENGTH:
            # Normally covered by Pydantic; retained as a defensive invariant.
            return JSONResponse(status_code=422, content={"detail": "Message is too long."})
        return analyze_message(payload.text)
    finally:
        body.clear()


@app.post("/api/analyze/document", response_model=MessageAnalysisResponse, response_model_exclude_none=True)
async def analyze_document(request: Request) -> MessageAnalysisResponse:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
    if content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Upload a PDF file using the application/pdf content type.")

    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="The PDF exceeds the 5 MB upload limit.")

    # Stream the request into bounded memory rather than Starlette's UploadFile
    # spool, which may write larger uploads to a temporary file.
    async with _pdf_analysis_slots:
        body = bytearray()
        try:
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_PDF_BYTES:
                    raise HTTPException(status_code=413, detail="The PDF exceeds the 5 MB upload limit.")
                body.extend(chunk)
            result = await run_in_threadpool(analyze_pdf, bytes(body))
            return result
        except DocumentAnalysisError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        finally:
            body.clear()
