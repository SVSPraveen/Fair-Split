import sys
import time
import json
import logging
from unittest.mock import patch, MagicMock
from pathlib import Path

# Ensure root workspace directory is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure utf-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("test_timeouts")

import httpx
import groq
import openai
from backend.llm_provider import LLMProvider, get_llm_provider
from backend.models import ReceiptData, DescriptionData
from backend.compute import compute_split
from fastapi.testclient import TestClient
from backend.main import app


def test_timeouts_and_fallbacks():
    print("=" * 80)
    print(" LLM PROVIDER TIMEOUT & FALLBACK VERIFICATION SUITE")
    print("=" * 80)

    provider = LLMProvider()

    # -------------------------------------------------------------
    # TEST 1: Primary Vision Timeout -> Fallback Execution
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print(">>> TEST 1: Gemini Vision Primary Timeout (Simulated 15s Timeout Event)")
    print("-" * 80)

    # Read real R1.png bytes for valid image payload
    r1_path = ROOT_DIR / "tests" / "sample_receipts" / "R1.png"
    if r1_path.exists():
        with open(r1_path, "rb") as f:
            valid_png_bytes = f.read()
    else:
        # Fallback 1x1 transparent PNG
        valid_png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )

    # Mock Gemini client to simulate a timeout after a measurable elapsed delay
    def mock_gemini_timeout(*args, **kwargs):
        time.sleep(0.25) # Simulate delay
        raise httpx.ReadTimeout("Request timed out after 15.0s (simulated)")

    # Mock OpenRouter client to return successful valid JSON
    mock_fallback_vision_resp = MagicMock()
    mock_fallback_vision_resp.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps({
                    "restaurant_name": "Timeout Cafe",
                    "bill_number": "TO-01",
                    "items": [
                        {"name": "Filter Coffee", "qty": 1.0, "unit_price": 50.0, "amount": 50.0}
                    ],
                    "subtotal": 50.0,
                    "discount": None,
                    "service_charge": None,
                    "tax": {"total_tax": 2.5},
                    "round_off": 0.5,
                    "grand_total": 53.0
                })
            )
        )
    ]

    with patch.object(provider._groq_client.chat.completions, "create", side_effect=httpx.ReadTimeout("Groq timeout")), \
         patch.object(provider._gemini_client.models, "generate_content", side_effect=mock_gemini_timeout), \
         patch.object(provider._openrouter_client.chat.completions, "create", return_value=mock_fallback_vision_resp):
        
        start_time = time.perf_counter()
        raw_text, used_fb, fb_reason = provider.generate_vision_with_status(
            prompt="Extract receipt",
            image_bytes=valid_png_bytes,
            timeout_seconds=15.0
        )
        elapsed = time.perf_counter() - start_time

    print(f"Elapsed Time before Fallback Handled: {elapsed:.3f}s")
    print(f"Used Fallback: {used_fb}")
    print(f"Fallback Reason: {fb_reason}")
    print(f"Response Preview: {raw_text[:120]}...")

    assert used_fb is True, "Expected used_fallback to be True on vision timeout"
    assert fb_reason == "timeout", f"Expected fallback_reason to be 'timeout', got '{fb_reason}'"
    print(">>> PASS: Vision timeout triggered OpenRouter fallback with exact 'timeout' reason.")

    # -------------------------------------------------------------
    # TEST 2: Primary Text Timeout -> Fallback Execution
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print(">>> TEST 2: Groq Text Primary Timeout (Simulated 10s Timeout Event)")
    print("-" * 80)

    # Mock Groq client to simulate a timeout after a delay
    def mock_groq_timeout(*args, **kwargs):
        time.sleep(0.20)
        raise groq.APITimeoutError(MagicMock(request=None))

    mock_fallback_text_resp = MagicMock()
    mock_fallback_text_resp.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps({
                    "people": ["Alice", "Bob"],
                    "payer": "Alice",
                    "item_assignments": [
                        {"item_name": "Filter Coffee", "consumed_by": ["Alice", "Bob"], "is_shared": True}
                    ],
                    "unmatched_mentions": [],
                    "unclear_references": [],
                    "parsing_assumptions": []
                })
            )
        )
    ]

    with patch.object(provider._groq_client.chat.completions, "create", side_effect=mock_groq_timeout), \
         patch.object(provider._openrouter_client.chat.completions, "create", return_value=mock_fallback_text_resp):
        
        start_time = time.perf_counter()
        raw_text, used_fb, fb_reason = provider.generate_text_with_status(
            prompt="Parse description",
            timeout_seconds=10.0
        )
        elapsed = time.perf_counter() - start_time

    print(f"Elapsed Time before Fallback Handled: {elapsed:.3f}s")
    print(f"Used Fallback: {used_fb}")
    print(f"Fallback Reason: {fb_reason}")
    print(f"Response Preview: {raw_text[:120]}...")

    assert used_fb is True, "Expected used_fallback to be True on text timeout"
    assert fb_reason == "timeout", f"Expected fallback_reason to be 'timeout', got '{fb_reason}'"
    print(">>> PASS: Text timeout triggered OpenRouter fallback with exact 'timeout' reason.")

    # -------------------------------------------------------------
    # TEST 3: Double Timeout (Both Primary & Fallback Fail) -> HTTP 504
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print(">>> TEST 3: Double Timeout (Both Primary & Fallback Time Out -> HTTP 504)")
    print("-" * 80)

    client = TestClient(app)

    def mock_double_timeout(*args, **kwargs):
        raise httpx.ReadTimeout("Both providers timed out")

    with patch.object(provider._gemini_client.models, "generate_content", side_effect=mock_double_timeout), \
         patch.object(provider._openrouter_client.chat.completions, "create", side_effect=mock_double_timeout), \
         patch("backend.extraction.get_vision_client", return_value=provider):
        
        start_time = time.perf_counter()
        response = client.post(
            "/split",
            json={
                "receipt_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "description": "Alice had coffee, Alice paid."
            }
        )
        elapsed = time.perf_counter() - start_time

    print(f"API Response Status Code: {response.status_code}")
    print(f"API Response Body: {response.json()}")
    assert response.status_code == 504, f"Expected 504 Gateway Timeout, got {response.status_code}"
    assert "timed out" in response.json()["detail"].lower()
    print(">>> PASS: Double timeout cleanly returned HTTP 504 Gateway Timeout without hanging or 500.")

    # -------------------------------------------------------------
    # TEST 4: Verification of Confidence Demotion & Exact Reasons in Compute
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print(">>> TEST 4: Confidence Field Differentiated Reason Verification")
    print("-" * 80)

    receipt_with_timeout = ReceiptData(
        restaurant_name="Timeout Diner",
        bill_number="TO-02",
        items=[
            {"name": "Sandwich", "qty": 1.0, "unit_price": 100.0, "amount": 100.0}
        ],
        subtotal=100.0,
        grand_total=100.0,
        used_fallback=True,
        fallback_reason="timeout"
    )

    desc_with_timeout = DescriptionData(
        people=["Ravi"],
        payer="Ravi",
        item_assignments=[
            {"item_name": "Sandwich", "consumed_by": ["Ravi"], "is_shared": False}
        ],
        used_fallback=True,
        fallback_reason="timeout"
    )

    split_res = compute_split(receipt_with_timeout, desc_with_timeout)
    print(f"Confidence Level: {split_res.confidence.level}")
    print("Confidence Reasons:")
    print(json.dumps(split_res.confidence.reasons, indent=2))

    assert split_res.confidence.level == "needs_review"
    assert any("Gemini timed out after 15s" in r for r in split_res.confidence.reasons)
    assert any("Groq timed out after 10s" in r for r in split_res.confidence.reasons)
    print(">>> PASS: Confidence reasons accurately reflect specific timeout triggers for both vision and text.")

    print("\n" + "=" * 80)
    print(" ALL TIMEOUT & FALLBACK VERIFICATIONS PASSED (4/4)")
    print("=" * 80)


if __name__ == "__main__":
    test_timeouts_and_fallbacks()
