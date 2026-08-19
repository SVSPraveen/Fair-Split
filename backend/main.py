import base64
import binascii
import logging
import time
import uuid
from typing import Dict, Any, Callable

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.models import SplitRequest, SplitResult
from backend.extraction import extract_receipt
from backend.description_parser import parse_description
from backend.compute import compute_split
from backend.llm_provider import validate_image_bytes
from backend.guardrails import sanitize_description

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate Limiter (20 requests/minute per IP on /split)
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=[])

# ---------------------------------------------------------------------------
# CORS — configurable via env for production, open for development
# ---------------------------------------------------------------------------
import os
_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
_cors_origins = [o.strip() for o in _ALLOWED_ORIGINS.split(",") if o.strip()] or ["*"]

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Fair-Split API",
    description="Production-grade itemized bill splitting and fairness computation engine",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request ID + Structured Logging Middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Callable) -> Response:
    """Attaches a UUID4 request_id to every request for traceability."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.monotonic()

    response = await call_next(request)

    latency_ms = int((time.monotonic() - start_time) * 1000)
    logger.info(
        f"request_id={request_id} method={request.method} path={request.url.path} "
        f"status={response.status_code} latency_ms={latency_ms} "
        f"ip={get_remote_address(request)}"
    )
    response.headers["X-Request-ID"] = request_id
    return response


# ---------------------------------------------------------------------------
# Startup Validation
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def validate_api_keys() -> None:
    """Warns at startup if any LLM API keys are missing (fail-fast for misconfiguration)."""
    missing = []
    for key_name in ["GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"]:
        if not os.getenv(key_name):
            missing.append(key_name)
    if missing:
        logger.warning(
            f"STARTUP WARNING: The following API keys are not set: {', '.join(missing)}. "
            "Some LLM providers will be unavailable. Ensure all keys are set in production."
        )
    else:
        logger.info("Startup: All LLM API keys present. Providers: Groq, Gemini, OpenRouter.")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health", summary="Health Check")
def health_check() -> Dict[str, Any]:
    """Returns service health and provider configuration status."""
    providers = {
        "groq": bool(os.getenv("GROQ_API_KEY")),
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
    }
    all_ok = any(providers.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "providers": providers,
        "version": "2.0.0"
    }


@app.post(
    "/split",
    response_model=SplitResult,
    response_model_by_alias=True,
    summary="Extract receipt, parse group description, and compute itemized bill split"
)
@limiter.limit("20/minute")
def split_bill(request: Request, body: SplitRequest) -> SplitResult:
    """End-to-end receipt extraction, natural language description parsing, and split calculation.

    Rate limited: 20 requests/minute per IP.

    Accepts:
        - receipt_base64: Base64 string of receipt image (PNG, JPEG, etc.)
        - description: Natural language text of consumption and payment

    Returns:
        SplitResult conforming to the assignment specification.
    """
    request_id = getattr(request.state, "request_id", "unknown")

    # 1a. Base64 decode (data URI prefix already stripped by SplitRequest validator)
    b64_str = body.receipt_base64
    if not b64_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="receipt_base64 cannot be empty."
        )

    try:
        image_bytes = base64.b64decode(b64_str, validate=True)
        if len(image_bytes) < 8:
            raise ValueError("Decoded byte stream is too short to be a valid image file.")
    except (binascii.Error, ValueError) as err:
        logger.warning(f"[{request_id}] Base64 decoding failed: {err}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base64 encoding for receipt image: {str(err)}"
        )

    # 1b. Pre-flight image validation (size, format, corruption)
    try:
        validate_image_bytes(image_bytes)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )

    # 1c. Sanitize description (prompt injection defense, length cap, control char strip)
    clean_description = sanitize_description(body.description)
    if not clean_description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="description cannot be empty. Describe who ate what and who paid."
        )

    # 2. Receipt OCR & Structured Extraction
    try:
        receipt_data = extract_receipt(image_bytes)
    except TimeoutError as timeout_err:
        logger.error(f"[{request_id}] Receipt extraction timed out: {timeout_err}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Receipt extraction timed out: {str(timeout_err)}"
        )
    except ValueError as val_err:
        # Includes non-receipt guard and partial extraction failures
        logger.warning(f"[{request_id}] Receipt extraction ValueError: {val_err}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(val_err)
        )
    except Exception as extract_err:
        logger.error(f"[{request_id}] Receipt extraction failed: {extract_err}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Receipt extraction failed: {str(extract_err)}"
        )

    # 3. Description Parsing against Known Receipt Items
    try:
        known_items = [item.name for item in receipt_data.items]
        description_data = parse_description(
            description=clean_description,
            known_items=known_items
        )
    except TimeoutError as timeout_err:
        logger.error(f"[{request_id}] Description parsing timed out: {timeout_err}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Description parsing timed out: {str(timeout_err)}"
        )
    except Exception as parse_err:
        logger.error(f"[{request_id}] Description parsing failed: {parse_err}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Description parsing failed: {str(parse_err)}"
        )

    # 4. Deterministic Bill Split Computation
    try:
        split_result = compute_split(
            receipt=receipt_data,
            description=description_data
        )
    except ValueError as val_err:
        logger.warning(f"[{request_id}] Computation rejected: {val_err}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(val_err)
        )
    except Exception as compute_err:
        logger.error(f"[{request_id}] Computation failed: {compute_err}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Split computation failed: {str(compute_err)}"
        )

    # Log outcome for monitoring
    logger.info(
        f"[{request_id}] Split complete: "
        f"grand_total=₹{receipt_data.grand_total:.2f} "
        f"people={len(split_result.per_person)} "
        f"confidence={split_result.confidence.level} "
        f"partial_extraction={receipt_data.partial_extraction} "
        f"used_fallback={receipt_data.used_fallback}"
    )

    return split_result
