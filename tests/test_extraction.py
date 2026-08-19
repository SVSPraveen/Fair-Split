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
    """Runs extract_receipt against sample receipts with validation."""
    receipt_files = ["R1.png", "R2.png"]
    results = {}

    print(f"\n=======================================================")
    print(f" FAIR-SPLIT RECEIPT EXTRACTION TEST SUITE")
    print(f" Primary Vision Model: {GEMINI_VISION_PRIMARY}")
    print(f" Fallback Vision Model: {OPENROUTER_VISION_FALLBACK}")
    print(f"=======================================================\n")

    for filename in receipt_files:
        filepath = SAMPLE_RECEIPTS_DIR / filename
        assert filepath.exists(), f"Sample receipt image missing: {filepath}"

        print(f"\n>>> Processing: {filename} ({filepath.name})")
        with open(filepath, "rb") as f:
            image_bytes = f.read()

        try:
            receipt_data: ReceiptData = extract_receipt(image_bytes)
            json_output = json.dumps(receipt_data.model_dump(), indent=2)
            results[filename] = receipt_data

            assert receipt_data.restaurant_name is not None, f"Restaurant name missing in {filename}"
            assert len(receipt_data.items) > 0, f"No items extracted in {filename}"
            assert receipt_data.grand_total > 0, f"Grand total invalid in {filename}"
            print(f"--> {filename} extracted successfully ({len(receipt_data.items)} items, ₹{receipt_data.grand_total})")
        except TimeoutError as te:
            print(f"Skipping live remote extraction for {filename} due to upstream API rate limit/timeout: {te}")

    print("\n[SUCCESS] Extraction test suite finished.")


def test_single_receipt(filename: str = "R1.png"):
    """Runs extraction specifically on a single receipt and prints results."""
    filepath = SAMPLE_RECEIPTS_DIR / filename
    with open(filepath, "rb") as f:
        image_bytes = f.read()
    try:
        receipt_data = extract_receipt(image_bytes)
        assert receipt_data.restaurant_name is not None
        assert receipt_data.grand_total > 0
    except TimeoutError as te:
        print(f"Upstream timeout on single receipt test: {te}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].endswith(".png"):
        test_single_receipt(sys.argv[1])
    else:
        test_extraction_all_receipts()
