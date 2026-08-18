import sys
import json
from pathlib import Path

# Ensure root workspace directory is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.models import (
    ReceiptData,
    ReceiptItem,
    DiscountDetail,
    TaxBreakdown,
    DescriptionData,
    ItemAssignment,
    SplitResult
)
from backend.compute import compute_split

# Verified ground truth datasets from Phase 1 (extraction) and Phase 2 (description parser)
GROUND_TRUTH_PAIRS = {
    "R1": {
        "receipt": ReceiptData(
            restaurant_name="BREW & BITE CAFE",
            bill_number="0142",
            items=[
                ReceiptItem(name="Cappuccino", qty=1.0, unit_price=180.0, amount=180.0),
                ReceiptItem(name="Grilled Chicken Sandwich", qty=1.0, unit_price=260.0, amount=260.0),
                ReceiptItem(name="Penne Arrabiata", qty=1.0, unit_price=320.0, amount=320.0),
                ReceiptItem(name="Fresh Lime Soda", qty=1.0, unit_price=120.0, amount=120.0),
                ReceiptItem(name="Brownie", qty=1.0, unit_price=160.0, amount=160.0),
            ],
            subtotal=1040.0,
            discount=None,
            service_charge=52.0,
            tax=TaxBreakdown(cgst=27.3, sgst=27.3, total_tax=54.6),
            round_off=0.4,
            grand_total=1147.0,
            extraction_flags=[]
        ),
        "description": DescriptionData(
            people=["Ravi", "Neha", "Sameer"],
            payer="Sameer",
            item_assignments=[
                ItemAssignment(item_name="Cappuccino", consumed_by=["Ravi"], is_shared=False),
                ItemAssignment(item_name="Grilled Chicken Sandwich", consumed_by=["Ravi"], is_shared=False),
                ItemAssignment(item_name="Penne Arrabiata", consumed_by=["Neha"], is_shared=False),
                ItemAssignment(item_name="Fresh Lime Soda", consumed_by=["Neha"], is_shared=False),
                ItemAssignment(item_name="Brownie", consumed_by=["Sameer"], is_shared=False),
            ],
            unmatched_mentions=[],
            unclear_references=[],
            parsing_assumptions=[
                "'sandwich' was interpreted as 'Grilled Chicken Sandwich' from known items.",
                "'pasta' was interpreted as 'Penne Arrabiata' from known items.",
                "'lime soda' was interpreted as 'Fresh Lime Soda' from known items."
            ]
        )
    },
    "R2": {
        "receipt": ReceiptData(
            restaurant_name="TAMARIND KITCHEN",
            bill_number="2207",
            items=[
                ReceiptItem(name="Paneer Butter Masala", qty=1.0, unit_price=320.0, amount=320.0),
                ReceiptItem(name="Dal Makhani", qty=1.0, unit_price=260.0, amount=260.0),
                ReceiptItem(name="Butter Naan", qty=4.0, unit_price=60.0, amount=240.0),
                ReceiptItem(name="Jeera Rice", qty=1.0, unit_price=180.0, amount=180.0),
                ReceiptItem(name="Gulab Jamun", qty=2.0, unit_price=60.0, amount=120.0),
                ReceiptItem(name="Masala Papad", qty=2.0, unit_price=50.0, amount=100.0),
            ],
            subtotal=1220.0,
            discount=None,
            service_charge=61.0,
            tax=TaxBreakdown(cgst=32.03, sgst=32.02, total_tax=64.05),
            round_off=-0.05,
            grand_total=1345.0,
            extraction_flags=[]
        ),
        "description": DescriptionData(
            people=["Aman", "Priya", "Karan", "Sara"],
            payer="Priya",
            item_assignments=[
                ItemAssignment(item_name="Gulab Jamun", consumed_by=["Priya", "Karan"], is_shared=True),
                ItemAssignment(item_name="Paneer Butter Masala", consumed_by=["Aman", "Priya", "Karan", "Sara"], is_shared=True),
                ItemAssignment(item_name="Dal Makhani", consumed_by=["Aman", "Priya", "Karan", "Sara"], is_shared=True),
                ItemAssignment(item_name="Butter Naan", consumed_by=["Aman", "Priya", "Karan", "Sara"], is_shared=True),
                ItemAssignment(item_name="Jeera Rice", consumed_by=["Aman", "Priya", "Karan", "Sara"], is_shared=True),
                ItemAssignment(item_name="Masala Papad", consumed_by=["Aman", "Priya", "Karan", "Sara"], is_shared=True),
            ],
            unmatched_mentions=[],
            unclear_references=[],
            parsing_assumptions=[
                "'Four of us' was interpreted as the four explicitly named individuals (Aman, Priya, Karan, Sara).",
                "The phrase 'Everything else was common to all four' was taken to mean that every known receipt item not otherwise specified is shared by all four people."
            ]
        )
    },
    "R3": {
        "receipt": ReceiptData(
            restaurant_name="THE DAILY GRIND",
            bill_number="1188",
            items=[
                ReceiptItem(name="Margherita Pizza", qty=1.0, unit_price=380.0, amount=380.0),
                ReceiptItem(name="Arrabiata Pasta", qty=1.0, unit_price=340.0, amount=340.0),
                ReceiptItem(name="Garlic Bread", qty=1.0, unit_price=160.0, amount=160.0),
                ReceiptItem(name="Craft Beer", qty=2.0, unit_price=250.0, amount=500.0),
                ReceiptItem(name="Virgin Mojito", qty=1.0, unit_price=180.0, amount=180.0),
            ],
            subtotal=1560.0,
            discount=None,
            service_charge=78.0,
            tax=TaxBreakdown(cgst=40.95, sgst=40.95, total_tax=81.9),
            round_off=0.1,
            grand_total=1720.0,
            extraction_flags=[]
        ),
        "description": DescriptionData(
            people=["Ishaan", "Meera", "Rohit"],
            payer="Rohit",
            item_assignments=[
                ItemAssignment(item_name="Margherita Pizza", consumed_by=["Ishaan", "Meera", "Rohit"], is_shared=True),
                ItemAssignment(item_name="Arrabiata Pasta", consumed_by=["Ishaan", "Meera", "Rohit"], is_shared=True),
                ItemAssignment(item_name="Garlic Bread", consumed_by=["Ishaan", "Meera", "Rohit"], is_shared=True),
                ItemAssignment(item_name="Craft Beer", consumed_by=["Ishaan", "Rohit"], is_shared=True),
                ItemAssignment(item_name="Virgin Mojito", consumed_by=["Meera"], is_shared=False),
            ],
            unmatched_mentions=[],
            unclear_references=[],
            parsing_assumptions=[
                "'Pizza' was interpreted as 'Margherita Pizza' from known items list.",
                "'pasta' was interpreted as 'Arrabiata Pasta' from known items list."
            ]
        )
    },
    "R4": {
        "receipt": ReceiptData(
            restaurant_name="SPICE ROUTE",
            bill_number="5521",
            items=[
                ReceiptItem(name="Chicken Biryani", qty=2.0, unit_price=280.0, amount=560.0),
                ReceiptItem(name="Veg Biryani", qty=1.0, unit_price=240.0, amount=240.0),
                ReceiptItem(name="Mutton Rogan Josh", qty=1.0, unit_price=420.0, amount=420.0),
                ReceiptItem(name="Raita", qty=2.0, unit_price=60.0, amount=120.0),
                ReceiptItem(name="Soft Drinks", qty=3.0, unit_price=60.0, amount=180.0),
            ],
            subtotal=1520.0,
            discount=DiscountDetail(amount=228.0, label="WELCOME15 -15%"),
            service_charge=76.0,
            tax=TaxBreakdown(cgst=34.2, sgst=34.2, total_tax=68.4),
            round_off=-0.4,
            grand_total=1436.0,
            extraction_flags=[]
        ),
        "description": DescriptionData(
            people=["Dev", "Nikhil", "Anjali", "Farah"],
            payer="Anjali",
            item_assignments=[
                ItemAssignment(item_name="Chicken Biryani", consumed_by=["Dev", "Nikhil"], is_shared=True),
                ItemAssignment(item_name="Veg Biryani", consumed_by=["Anjali"], is_shared=False),
                ItemAssignment(item_name="Mutton Rogan Josh", consumed_by=["Farah"], is_shared=False),
                ItemAssignment(item_name="Raita", consumed_by=["Dev", "Nikhil", "Anjali", "Farah"], is_shared=True),
                ItemAssignment(item_name="Soft Drinks", consumed_by=["Dev", "Nikhil", "Anjali", "Farah"], is_shared=True),
            ],
            unmatched_mentions=[],
            unclear_references=[],
            parsing_assumptions=[
                "'rogan josh' interpreted as 'Mutton Rogan Josh'",
                "'we' was interpreted as the four named individuals: Dev, Nikhil, Anjali, Farah"
            ]
        )
    }
}


def run_compute_tests():
    print("\n=======================================================")
    print(" FAIR-SPLIT COMPUTE ENGINE TEST SUITE (R1-R4)")
    print("=======================================================\n")

    results = {}

    for case_id, case_data in GROUND_TRUTH_PAIRS.items():
        receipt = case_data["receipt"]
        description = case_data["description"]

        print(f"\n==================== FULL RESULT FOR {case_id} ====================")
        split_result: SplitResult = compute_split(receipt=receipt, description=description)
        results[case_id] = split_result

        # Serialize to formatted JSON
        json_output = json.dumps(split_result.model_dump(by_alias=True), indent=2)
        print(json_output)

        # Assertions
        assert split_result.reconciliation.matches_bill is True, (
            f"{case_id} failed reconciliation: {split_result.reconciliation}"
        )
        assert split_result.reconciliation.sum_of_person_totals == receipt.grand_total, (
            f"{case_id} sum ({split_result.reconciliation.sum_of_person_totals}) != grand_total ({receipt.grand_total})"
        )

        if description.payer:
            assert split_result.paid_by == description.payer
            expected_settle_count = len(description.people) - 1
            assert len(split_result.settle_up) == expected_settle_count, (
                f"Expected {expected_settle_count} settle up transactions, got {len(split_result.settle_up)}"
            )

        print(f"\n--> Reconciliation: Sum = {split_result.reconciliation.sum_of_person_totals}, Grand Total = {receipt.grand_total} (MATCH)")
        print("-" * 55)

    print("\n[SUCCESS] All 4 compute engine test cases executed and reconciled perfectly!")
    return results


if __name__ == "__main__":
    run_compute_tests()
