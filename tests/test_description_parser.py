import os
import sys
import json
from pathlib import Path

# Ensure root workspace directory is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.extraction import extract_receipt
from backend.description_parser import parse_description
from backend.models import DescriptionData

SAMPLE_RECEIPTS_DIR = Path(__file__).parent / "sample_receipts"

# Real verbatim descriptions from assignment brief (R1-R4)
TEST_CASES = {
    "R1": {
        "receipt_file": "R1.png",
        "description": "Three of us — Ravi, Neha, Sameer. Ravi had the cappuccino and the sandwich. Neha had the pasta and the lime soda. Sameer had the brownie. Sameer paid.",
        "expected_payer": "Sameer",
        "expected_people_count": 3,
    },
    "R2": {
        "receipt_file": "R2.png",
        "description": "Four of us: Aman, Priya, Karan, Sara. The Gulab Jamun was shared just by Priya and Karan. Everything else was common to all four. Priya paid.",
        "expected_payer": "Priya",
        "expected_people_count": 4,
    },
    "R3": {
        "receipt_file": "R3.png",
        "description": "Ishaan, Meera, Rohit. Pizza, pasta and garlic bread shared equally by all three. The two beers were Ishaan and Rohit only. The mojito was Meera's. Rohit paid.",
        "expected_payer": "Rohit",
        "expected_people_count": 3,
    },
    "R4": {
        "receipt_file": "R4.png",
        "description": "Dev and Nikhil each had a chicken biryani. Anjali had the veg biryani. Farah had the rogan josh. The raita and soft drinks were common to all four. We used a 15% off coupon. Anjali paid.",
        "expected_payer": "Anjali",
        "expected_people_count": 4,
    }
}


def run_description_parser_tests():
    print("\n=======================================================")
    print(" FAIR-SPLIT DESCRIPTION PARSER TEST SUITE (VERBATIM R1-R4)")
    print("=======================================================\n")

    results = {}

    for case_id, case_info in TEST_CASES.items():
        receipt_path = SAMPLE_RECEIPTS_DIR / case_info["receipt_file"]
        assert receipt_path.exists(), f"Receipt file {receipt_path} not found"

        print(f"\n--- [Test Case {case_id}] ({case_info['receipt_file']}) ---")
        
        # 1. Extract receipt to get live known items from Phase 1
        with open(receipt_path, "rb") as f:
            image_bytes = f.read()
        receipt_data = extract_receipt(image_bytes)
        known_items = [item.name for item in receipt_data.items]
        print(f"Known Receipt Items: {known_items}")
        print(f"Verbatim Description Text:\n  \"{case_info['description']}\"")

        # 2. Parse description
        parsed_data: DescriptionData = parse_description(
            description=case_info["description"],
            known_items=known_items
        )
        results[case_id] = parsed_data

        # 3. Print parsed JSON
        formatted_json = json.dumps(parsed_data.model_dump(), indent=2)
        print(f"\n[Parsed DescriptionData JSON for {case_id}]:")
        print(formatted_json)

        # 4. Validations
        assert len(parsed_data.people) == case_info["expected_people_count"], (
            f"Expected {case_info['expected_people_count']} people, got {parsed_data.people}"
        )
        if case_info["expected_payer"] is None:
            assert parsed_data.payer is None, f"Expected payer to be None, got {parsed_data.payer}"
        else:
            assert parsed_data.payer == case_info["expected_payer"], (
                f"Expected payer {case_info['expected_payer']}, got {parsed_data.payer}"
            )

        print(f"--> Validation PASSED for {case_id}")
        print("-" * 55)

    print("\n[SUCCESS] All 4 verbatim description parsing test cases passed!")
    return results


if __name__ == "__main__":
    run_description_parser_tests()
