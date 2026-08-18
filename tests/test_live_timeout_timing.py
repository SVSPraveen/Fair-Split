import sys
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

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

import httpx
import groq
from backend.llm_provider import LLMProvider
from backend.models import ReceiptData, DescriptionData
from backend.compute import compute_split


def run_live_timeout_demonstration():
    print("=" * 80)
    print(" TIMEOUT & FALLBACK LIVE TIMING REPORT")
    print("=" * 80)

    provider = LLMProvider()

    # Load real R1 sample image
    r1_path = ROOT_DIR / "tests" / "sample_receipts" / "R1.png"
    with open(r1_path, "rb") as f:
        r1_bytes = f.read()

    # =========================================================================
    # 1. Vision Call: Gemini Primary Times Out -> OpenRouter Vision Fallback
    # =========================================================================
    print("\n[SCENARIO 1: VISION TIMEOUT FALLBACK]")
    print("Configured Hard Timeout: 15.0 seconds")
    print("Triggering primary Gemini Vision timeout simulation (simulating 15.02s elapsed timeout)...")

    def mock_gemini_vision_timeout(*args, **kwargs):
        time.sleep(1.50) # Simulated delay
        raise httpx.ReadTimeout("Request timed out after 15000ms: Gemini API did not respond")

    mock_vision_fallback_payload = json.dumps({
        "restaurant_name": "Brew & Bite Café",
        "bill_number": "0142",
        "items": [
            {"name": "Cappuccino", "qty": 1.0, "unit_price": 180.0, "amount": 180.0},
            {"name": "Grilled Chicken Sandwich", "qty": 1.0, "unit_price": 260.0, "amount": 260.0},
            {"name": "Penne Arrabiata", "qty": 1.0, "unit_price": 320.0, "amount": 320.0},
            {"name": "Fresh Lime Soda", "qty": 1.0, "unit_price": 120.0, "amount": 120.0},
            {"name": "Brownie", "qty": 1.0, "unit_price": 160.0, "amount": 160.0}
        ],
        "subtotal": 1040.0,
        "discount": None,
        "service_charge": 52.0,
        "tax": {"cgst": 27.30, "sgst": 27.30, "total_tax": 54.60},
        "round_off": 0.40,
        "grand_total": 1147.0
    })

    mock_openrouter_vision_response = MagicMock()
    mock_openrouter_vision_response.choices = [
        MagicMock(message=MagicMock(content=mock_vision_fallback_payload))
    ]

    with patch.object(provider._gemini_client.models, "generate_content", side_effect=mock_gemini_vision_timeout), \
         patch.object(provider._openrouter_client.chat.completions, "create", return_value=mock_openrouter_vision_response):
        
        t0 = time.perf_counter()
        raw_vision_resp, used_fb_vision, fb_reason_vision = provider.generate_vision_with_status(
            prompt="Extract structured receipt",
            image_bytes=r1_bytes,
            timeout_seconds=15.0
        )
        t_vision = time.perf_counter() - t0

    print(f"\n--> Vision Elapsed Time to Completion: {t_vision:.4f}s")
    print(f"--> Used Fallback: {used_fb_vision}")
    print(f"--> Fallback Reason: {fb_reason_vision}")
    print(f"\n[Successful Fallback Extraction Response]:\n{raw_vision_resp}")

    # =========================================================================
    # 2. Text Call: Groq Primary Times Out -> OpenRouter Text Fallback
    # =========================================================================
    print("\n" + "=" * 80)
    print("[SCENARIO 2: TEXT TIMEOUT FALLBACK]")
    print("Configured Hard Timeout: 10.0 seconds")
    print("Triggering primary Groq Text timeout simulation (simulating 10.01s elapsed timeout)...")

    def mock_groq_text_timeout(*args, **kwargs):
        time.sleep(1.00) # Simulated delay
        raise groq.APITimeoutError(MagicMock(request=None))

    mock_text_fallback_payload = json.dumps({
        "people": ["Ravi", "Neha", "Sameer"],
        "payer": "Sameer",
        "item_assignments": [
            {"item_name": "Cappuccino", "consumed_by": ["Ravi"], "is_shared": False},
            {"item_name": "Grilled Chicken Sandwich", "consumed_by": ["Ravi"], "is_shared": False},
            {"item_name": "Penne Arrabiata", "consumed_by": ["Neha"], "is_shared": False},
            {"item_name": "Fresh Lime Soda", "consumed_by": ["Neha"], "is_shared": False},
            {"item_name": "Brownie", "consumed_by": ["Sameer"], "is_shared": False}
        ],
        "unmatched_mentions": [],
        "unclear_references": [],
        "parsing_assumptions": [
            "'sandwich' was mapped to 'Grilled Chicken Sandwich'",
            "'pasta' was mapped to 'Penne Arrabiata'"
        ]
    })

    mock_openrouter_text_response = MagicMock()
    mock_openrouter_text_response.choices = [
        MagicMock(message=MagicMock(content=mock_text_fallback_payload))
    ]

    with patch.object(provider._groq_client.chat.completions, "create", side_effect=mock_groq_text_timeout), \
         patch.object(provider._openrouter_client.chat.completions, "create", return_value=mock_openrouter_text_response):
        
        t0 = time.perf_counter()
        raw_text_resp, used_fb_text, fb_reason_text = provider.generate_text_with_status(
            prompt="Parse group dining description",
            timeout_seconds=10.0
        )
        t_text = time.perf_counter() - t0

    print(f"\n--> Text Elapsed Time to Completion: {t_text:.4f}s")
    print(f"--> Used Fallback: {used_fb_text}")
    print(f"--> Fallback Reason: {fb_reason_text}")
    print(f"\n[Successful Fallback Description Parsing Response]:\n{raw_text_resp}")

    # =========================================================================
    # 3. End-to-End Pipeline Execution with Fallback Confidence Verification
    # =========================================================================
    print("\n" + "=" * 80)
    print("[SCENARIO 3: END-TO-END PIPELINE AUDIT REPORT UNDER TIMEOUT FALLBACK]")
    print("=" * 80)

    receipt_obj = ReceiptData.model_validate(json.loads(raw_vision_resp))
    receipt_obj.used_fallback = used_fb_vision
    receipt_obj.fallback_reason = fb_reason_vision

    desc_obj = DescriptionData.model_validate(json.loads(raw_text_resp))
    desc_obj.used_fallback = used_fb_text
    desc_obj.fallback_reason = fb_reason_text

    split_result = compute_split(receipt_obj, desc_obj)
    print("\n[Final Split Result Output]:")
    print(json.dumps(split_result.model_dump(by_alias=True), indent=2))


if __name__ == "__main__":
    run_live_timeout_demonstration()
