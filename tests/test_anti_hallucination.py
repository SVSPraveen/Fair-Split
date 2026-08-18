import sys
import json
from pathlib import Path

# Ensure utf-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.models import ReceiptData, ReceiptItem, DescriptionData, ItemAssignment, TaxBreakdown, DiscountDetail
from backend.compute import compute_split
from backend.extraction import _run_self_checks


def test_anti_hallucination():
    print("=" * 70)
    print(" ANTI-HALLUCINATION MECHANISMS VERIFICATION SUITE")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. Per-Item Line Math Check Verification
    # -------------------------------------------------------------
    print("\n[TEST 1] Per-Item Line Math Check (qty * unit_price != amount)...")
    mismatched_receipt = ReceiptData(
        restaurant_name="Bad Math Cafe",
        items=[
            ReceiptItem(name="Cappuccino", qty=2.0, unit_price=150.0, amount=350.0), # 2 * 150 = 300 != 350
            ReceiptItem(name="Croissant", qty=1.0, unit_price=120.0, amount=120.0)
        ],
        subtotal=470.0,
        grand_total=470.0
    )
    flags = _run_self_checks(mismatched_receipt)
    print("Generated flags:", flags)
    assert any("Line item math mismatch for 'Cappuccino'" in f for f in flags), "Failed to catch per-item mismatch!"
    print(">>> PASS: Per-item math check flagged misread price/qty successfully.")

    # -------------------------------------------------------------
    # 2. Clean Case Verification: Scenario R1 (Brew & Bite Cafe)
    # -------------------------------------------------------------
    print("\n[TEST 2] Scenario R1 (Brew & Bite Cafe) - Clean Case...")
    r1_receipt = ReceiptData(
        restaurant_name="Brew & Bite Café",
        bill_number="0142",
        items=[
            ReceiptItem(name="Cappuccino", qty=1.0, unit_price=180.0, amount=180.0),
            ReceiptItem(name="Grilled Chicken Sandwich", qty=1.0, unit_price=260.0, amount=260.0),
            ReceiptItem(name="Penne Arrabiata", qty=1.0, unit_price=320.0, amount=320.0),
            ReceiptItem(name="Fresh Lime Soda", qty=1.0, unit_price=120.0, amount=120.0),
            ReceiptItem(name="Brownie", qty=1.0, unit_price=160.0, amount=160.0),
        ],
        subtotal=1040.0,
        service_charge=52.0,
        tax=TaxBreakdown(total_tax=54.60),
        round_off=0.40,
        grand_total=1147.0
    )
    r1_desc = DescriptionData(
        people=["Ravi", "Neha", "Sameer"],
        payer="Sameer",
        item_assignments=[
            ItemAssignment(item_name="Cappuccino", consumed_by=["Ravi"], is_shared=False),
            ItemAssignment(item_name="Grilled Chicken Sandwich", consumed_by=["Ravi"], is_shared=False),
            ItemAssignment(item_name="Penne Arrabiata", consumed_by=["Neha"], is_shared=False),
            ItemAssignment(item_name="Fresh Lime Soda", consumed_by=["Neha"], is_shared=False),
            ItemAssignment(item_name="Brownie", consumed_by=["Sameer"], is_shared=False),
        ]
    )
    r1_split = compute_split(r1_receipt, r1_desc)
    print(f"R1 Confidence: {r1_split.confidence.model_dump_json(indent=2)}")
    assert r1_split.confidence.level == "high", f"R1 expected high, got {r1_split.confidence.level}"
    print(">>> PASS: R1 marked as HIGH confidence.")

    # -------------------------------------------------------------
    # 3. Clean Case Verification: Scenario R2 (Tamarind Kitchen)
    # -------------------------------------------------------------
    print("\n[TEST 3] Scenario R2 (Tamarind Kitchen) - Clean Case...")
    r2_receipt = ReceiptData(
        restaurant_name="Tamarind Kitchen",
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
        service_charge=61.0,
        tax=TaxBreakdown(total_tax=64.05),
        round_off=-0.05,
        grand_total=1345.0
    )
    r2_desc = DescriptionData(
        people=["Aman", "Priya", "Karan", "Sara"],
        payer="Priya",
        item_assignments=[
            ItemAssignment(item_name="Paneer Butter Masala", consumed_by=["Aman", "Priya", "Karan", "Sara"], is_shared=True),
            ItemAssignment(item_name="Dal Makhani", consumed_by=["Aman", "Priya", "Karan", "Sara"], is_shared=True),
            ItemAssignment(item_name="Butter Naan", consumed_by=["Aman", "Priya", "Karan", "Sara"], is_shared=True),
            ItemAssignment(item_name="Jeera Rice", consumed_by=["Aman", "Priya", "Karan", "Sara"], is_shared=True),
            ItemAssignment(item_name="Gulab Jamun", consumed_by=["Priya", "Karan"], is_shared=True),
            ItemAssignment(item_name="Masala Papad", consumed_by=["Aman", "Priya", "Karan", "Sara"], is_shared=True),
        ]
    )
    r2_split = compute_split(r2_receipt, r2_desc)
    print(f"R2 Confidence: {r2_split.confidence.model_dump_json(indent=2)}")
    assert r2_split.confidence.level == "high", f"R2 expected high, got {r2_split.confidence.level}"
    print(">>> PASS: R2 marked as HIGH confidence.")

    # -------------------------------------------------------------
    # 4. Clean Case Verification: Scenario R3 (The Daily Grind)
    # -------------------------------------------------------------
    print("\n[TEST 4] Scenario R3 (The Daily Grind) - Clean Case...")
    r3_receipt = ReceiptData(
        restaurant_name="The Daily Grind",
        bill_number="1188",
        items=[
            ReceiptItem(name="Margherita Pizza", qty=1.0, unit_price=380.0, amount=380.0),
            ReceiptItem(name="Arrabiata Pasta", qty=1.0, unit_price=340.0, amount=340.0),
            ReceiptItem(name="Garlic Bread", qty=1.0, unit_price=160.0, amount=160.0),
            ReceiptItem(name="Craft Beer", qty=2.0, unit_price=250.0, amount=500.0),
            ReceiptItem(name="Virgin Mojito", qty=1.0, unit_price=180.0, amount=180.0),
        ],
        subtotal=1560.0,
        service_charge=78.0,
        tax=TaxBreakdown(total_tax=81.90),
        round_off=0.10,
        grand_total=1720.0
    )
    r3_desc = DescriptionData(
        people=["Ishaan", "Meera", "Rohit"],
        payer="Rohit",
        item_assignments=[
            ItemAssignment(item_name="Margherita Pizza", consumed_by=["Ishaan", "Meera", "Rohit"], is_shared=True),
            ItemAssignment(item_name="Arrabiata Pasta", consumed_by=["Ishaan", "Meera", "Rohit"], is_shared=True),
            ItemAssignment(item_name="Garlic Bread", consumed_by=["Ishaan", "Meera", "Rohit"], is_shared=True),
            ItemAssignment(item_name="Craft Beer", consumed_by=["Ishaan", "Rohit"], is_shared=True),
            ItemAssignment(item_name="Virgin Mojito", consumed_by=["Meera"], is_shared=False),
        ]
    )
    r3_split = compute_split(r3_receipt, r3_desc)
    print(f"R3 Confidence: {r3_split.confidence.model_dump_json(indent=2)}")
    assert r3_split.confidence.level == "high", f"R3 expected high, got {r3_split.confidence.level}"
    print(">>> PASS: R3 marked as HIGH confidence.")

    # -------------------------------------------------------------
    # 5. Clean Case Verification: Scenario R4 (Spice Route with Discount)
    # -------------------------------------------------------------
    print("\n[TEST 5] Scenario R4 (Spice Route) - Clean Case...")
    r4_receipt = ReceiptData(
        restaurant_name="Spice Route",
        bill_number="4412",
        items=[
            ReceiptItem(name="Chicken Biryani", qty=2.0, unit_price=380.0, amount=760.0),
            ReceiptItem(name="Veg Biryani", qty=1.0, unit_price=320.0, amount=320.0),
            ReceiptItem(name="Mutton Rogan Josh", qty=1.0, unit_price=440.0, amount=440.0),
        ],
        subtotal=1520.0,
        discount=DiscountDetail(amount=228.0, label="WELCOME15 (-15%)"),
        service_charge=76.0,
        tax=TaxBreakdown(total_tax=68.40),
        round_off=-0.40,
        grand_total=1436.0
    )
    r4_desc = DescriptionData(
        people=["Dev", "Nikhil", "Anjali", "Farah"],
        payer="Anjali",
        item_assignments=[
            ItemAssignment(item_name="Chicken Biryani", consumed_by=["Dev", "Nikhil"], is_shared=True),
            ItemAssignment(item_name="Veg Biryani", consumed_by=["Anjali"], is_shared=False),
            ItemAssignment(item_name="Mutton Rogan Josh", consumed_by=["Farah"], is_shared=False),
        ]
    )
    r4_split = compute_split(r4_receipt, r4_desc)
    print(f"R4 Confidence: {r4_split.confidence.model_dump_json(indent=2)}")
    assert r4_split.confidence.level == "high", f"R4 expected high, got {r4_split.confidence.level}"
    print(">>> PASS: R4 marked as HIGH confidence.")

    # -------------------------------------------------------------
    # 6. Edge Case: Case 7 (Packaging Fee - Unassigned item)
    # -------------------------------------------------------------
    print("\n[TEST 6] Case 7 (Packaging Fee - Needs Review Trigger)...")
    case7_receipt = ReceiptData(
        restaurant_name="Biryani Express",
        bill_number="EDGE-07",
        items=[
            ReceiptItem(name="Hyderabadi Biryani", qty=1.0, unit_price=350.0, amount=350.0),
            ReceiptItem(name="Mirchi Salan", qty=1.0, unit_price=100.0, amount=100.0),
            ReceiptItem(name="Container & Packaging Charge", qty=1.0, unit_price=40.0, amount=40.0)
        ],
        subtotal=490.0,
        tax=TaxBreakdown(total_tax=24.50),
        round_off=-0.50,
        grand_total=514.0
    )
    case7_desc = DescriptionData(
        people=["Karan", "Kabir"],
        payer="Karan",
        item_assignments=[
            ItemAssignment(item_name="Hyderabadi Biryani", consumed_by=["Karan"], is_shared=False),
            ItemAssignment(item_name="Mirchi Salan", consumed_by=["Kabir"], is_shared=False)
        ]
    )
    case7_split = compute_split(case7_receipt, case7_desc)
    print(f"Case 7 Confidence: {case7_split.confidence.model_dump_json(indent=2)}")
    assert case7_split.confidence.level == "needs_review", f"Case 7 expected needs_review, got {case7_split.confidence.level}"
    assert any("Container & Packaging Charge" in r for r in case7_split.confidence.reasons)
    print(">>> PASS: Case 7 correctly marked as NEEDS_REVIEW with reason.")

    # -------------------------------------------------------------
    # 7. Edge Case: R5 (The Irregular Cafe - Subtotal Mismatch)
    # -------------------------------------------------------------
    print("\n[TEST 7] Scenario R5 (Subtotal Mismatch - Needs Review Trigger)...")
    r5_receipt = ReceiptData(
        restaurant_name="The Irregular Cafe",
        bill_number="0099",
        items=[
            ReceiptItem(name="Cold Brew", qty=2.0, unit_price=180.0, amount=360.0),
            ReceiptItem(name="Avocado Toast", qty=1.0, unit_price=340.0, amount=340.0),
            ReceiptItem(name="Pancakes", qty=1.0, unit_price=280.0, amount=280.0),
        ],
        subtotal=1000.0, # Actual sum is 980.00
        service_charge=50.0,
        tax=TaxBreakdown(total_tax=50.0),
        round_off=0.0,
        grand_total=1100.0
    )
    r5_receipt.extraction_flags = _run_self_checks(r5_receipt)
    r5_desc = DescriptionData(
        people=["Rohan", "Sonal"],
        payer="Rohan",
        item_assignments=[
            ItemAssignment(item_name="Cold Brew", consumed_by=["Rohan", "Sonal"], is_shared=True),
            ItemAssignment(item_name="Avocado Toast", consumed_by=["Rohan"], is_shared=False),
            ItemAssignment(item_name="Pancakes", consumed_by=["Sonal"], is_shared=False),
        ]
    )
    r5_split = compute_split(r5_receipt, r5_desc)
    print(f"R5 Confidence: {r5_split.confidence.model_dump_json(indent=2)}")
    assert r5_split.confidence.level == "needs_review", f"R5 expected needs_review, got {r5_split.confidence.level}"
    assert any("Subtotal mismatch" in r for r in r5_split.confidence.reasons)
    print(">>> PASS: R5 correctly marked as NEEDS_REVIEW with subtotal mismatch reason.")

    print("\n" + "=" * 70)
    print(" ALL ANTI-HALLUCINATION TESTS PASSED (7/7)")
    print("=" * 70)


if __name__ == "__main__":
    test_anti_hallucination()
