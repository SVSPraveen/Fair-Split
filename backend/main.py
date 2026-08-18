import base64
import binascii
import logging
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.models import SplitRequest, SplitResult
from backend.extraction import extract_receipt
from backend.description_parser import parse_description
from backend.compute import compute_split

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Fair-Split API",
    description="Itemized bill splitting and fairness computation engine",
    version="1.0.0"
)

# Configure CORS - allow all origins per ground rules
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", summary="Health Check")
def health_check() -> Dict[str, str]:
    """Returns basic service health status."""
    return {"status": "ok"}


@app.post(
    "/split",
    response_model=SplitResult,
    response_model_by_alias=True,
    summary="Extract receipt, parse group description, and compute itemized bill split"
)
def split_bill(request: SplitRequest) -> SplitResult:
    """End-to-end receipt extraction, natural language description parsing, and split calculation.
    
    Accepts:
        - receipt_base64: Base64 string of receipt image (PNG, JPEG, etc.)
        - description: Natural language text of consumption and payment
        
    Returns:
        SplitResult conforming to the assignment specification.
    """
    # 1. Base64 validation and decoding
    b64_str = request.receipt_base64.strip()
    if not b64_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="receipt_base64 cannot be empty."
        )

    # Clean out accidental data URI prefix if provided
    if b64_str.startswith("data:"):
        b64_str = b64_str.split(",", 1)[-1].strip()

    try:
        image_bytes = base64.b64decode(b64_str, validate=True)
        if len(image_bytes) < 8:
            raise ValueError("Decoded byte stream is too short to be a valid image file.")
    except (binascii.Error, ValueError) as err:
        logger.warning(f"Base64 decoding failed: {err}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base64 encoding for receipt image: {str(err)}"
        )

    # 2. Receipt OCR & Structured Extraction
    try:
        receipt_data = extract_receipt(image_bytes)
    except TimeoutError as timeout_err:
        logger.error(f"Receipt extraction timed out: {timeout_err}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Receipt extraction timed out: {str(timeout_err)}"
        )
    except Exception as extract_err:
        logger.error(f"Receipt extraction failed: {extract_err}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Receipt extraction failed: {str(extract_err)}"
        )

    # 3. Description Parsing against Known Receipt Items
    try:
        known_items = [item.name for item in receipt_data.items]
        description_data = parse_description(
            description=request.description,
            known_items=known_items
        )
    except TimeoutError as timeout_err:
        logger.error(f"Description parsing timed out: {timeout_err}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Description parsing timed out: {str(timeout_err)}"
        )
    except Exception as parse_err:
        logger.error(f"Description parsing failed: {parse_err}")
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
        return split_result
    except Exception as compute_err:
        logger.error(f"Computation failed: {compute_err}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Split computation failed: {str(compute_err)}"
        )
