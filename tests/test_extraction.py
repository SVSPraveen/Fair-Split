import os
import sys
from pathlib import Path

# Ensure root workspace directory is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import json
from backend.extraction import extract_receipt
from backend.llm_provider import (
    GEMINI_VISION_PRIMARY,
    OPENROUTER_VISION_FALLBACK,
    get_vision_client,
    get_text_client
)
from backend.models import ReceiptData

SAMPLE_RECEIPTS_DIR = Path(__file__).parent / "sample_receipts"


def test_extraction_all_receipts():
    """Runs extract_receipt against all sample receipts (R1-R5)

    using the Gemini Flash primary vision model.
    """
    receipt_files = ["R1.png", "R2.png", "R3.png", "R4.png", "R5.png"]
    results = {}

    print(f"\n=======================================================")
    print(f" FAIR-SPLIT RECEIPT EXTRACTION TEST SUITE")
    print(f" Primary Vision Model: {GEMINI_VISION_PRIMARY}")
    print(f" Fallback Vision Model: {OPENROUTER_VISION_FALLBACK}")
    print(f"=======================================================\n")

    for filename in receipt_files:
        filepath = SAMPLE_RECEIPTS_DIR / filename
        assert filepath.exists(), f"Sample receipt image missing: {filepath}"

        print(f"\n>>> Processing: {filename} ({filepath.name}) via Primary Vision Client")
        with open(filepath, "rb") as f:
            image_bytes = f.read()

        receipt_data: ReceiptData = extract_receipt(image_bytes)

        # Serialize to JSON formatted string
        json_output = json.dumps(receipt_data.model_dump(), indent=2)
        results[filename] = receipt_data

        print(f"\n[Result JSON for {filename}]:")
        print(json_output)
        
        print(f"\n[Extraction Flags]:")
        if receipt_data.extraction_flags:
            for flag in receipt_data.extraction_flags:
                print(f"  [FLAG] {flag}")
        else:
            print("  (No flags - all mathematical checks passed!)")

        # Assertions
        assert receipt_data.restaurant_name is not None, f"Restaurant name missing in {filename}"
        assert len(receipt_data.items) > 0, f"No items extracted in {filename}"
        assert receipt_data.grand_total > 0, f"Grand total invalid in {filename}"
        print("-" * 55)

    print("\n[SUCCESS] All receipts processed and validated successfully with Gemini Vision!")
    return results


def test_single_receipt(filename: str = "R5.png"):
    """Runs extraction specifically on a single receipt and prints results."""
    filepath = SAMPLE_RECEIPTS_DIR / filename
    with open(filepath, "rb") as f:
        image_bytes = f.read()
    receipt_data = extract_receipt(image_bytes)
    print(f"\n==================== RAW RESULT FOR {filename} ====================")
    print(json.dumps(receipt_data.model_dump(), indent=2))
    print("=================================================================")
    return receipt_data


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].endswith(".png"):
        test_single_receipt(sys.argv[1])
    else:
        test_extraction_all_receipts()
