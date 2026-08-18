import sys
import json
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

from backend.models import ReceiptData, ReceiptItem, DescriptionData, ItemAssignment, TaxBreakdown
from backend.cross_check import cross_check_extraction_and_parsing
from backend.compute import compute_split


def run_cross_check_demonstration():
    print("=" * 80)
    print(" CROSS-CHECK MODULE DEMONSTRATION & FAILURE PROBE")
    print("=" * 80)

    # 4-Item Base Receipt
    receipt_4items = ReceiptData(
        restaurant_name="Grand Diner",
        bill_number="GD-101",
        items=[
            ReceiptItem(name="Classic Burger", qty=1.0, unit_price=300.0, amount=300.0),
            ReceiptItem(name="French Fries", qty=1.0, unit_price=150.0, amount=150.0),
            ReceiptItem(name="Coke", qty=1.0, unit_price=80.0, amount=80.0),
            ReceiptItem(name="New York Cheesecake", qty=1.0, unit_price=220.0, amount=220.0),
        ],
        subtotal=750.0,
        tax=TaxBreakdown(total_tax=37.50),
        round_off=0.50,
        grand_total=788.0
    )

    # -------------------------------------------------------------
    # CASE A: Item Accounted for in unclear_references
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print(">>> CASE A: Item unassigned but ACCOUNTED FOR in unclear_references")
    print("-" * 80)
    desc_case_a = DescriptionData(
        people=["Alice", "Bob"],
        payer="Alice",
        item_assignments=[
            ItemAssignment(item_name="Classic Burger", consumed_by=["Alice"], is_shared=False),
            ItemAssignment(item_name="French Fries", consumed_by=["Bob"], is_shared=False),
            ItemAssignment(item_name="Coke", consumed_by=["Bob"], is_shared=False),
        ],
        unclear_references=["New York Cheesecake was left on table, unclear who ordered it"],
        unmatched_mentions=[]
    )

    flags_a = cross_check_extraction_and_parsing(receipt_4items, desc_case_a)
    result_a = compute_split(receipt_4items, desc_case_a)

    print("\n[Cross-Check Flags for Case A]:")
    print(json.dumps(flags_a, indent=2))
    print("\n[Full Output for Case A]:")
    print(json.dumps(result_a.model_dump(by_alias=True), indent=2))

    # -------------------------------------------------------------
    # CASE B: Deliberate Bug — Item SILENTLY VANISHED
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print(">>> CASE B: Deliberate Pipeline Bug — Item SILENTLY DROPPED (no record)")
    print("-" * 80)
    desc_case_b = DescriptionData(
        people=["Alice", "Bob"],
        payer="Alice",
        item_assignments=[
            ItemAssignment(item_name="Classic Burger", consumed_by=["Alice"], is_shared=False),
            ItemAssignment(item_name="French Fries", consumed_by=["Bob"], is_shared=False),
            ItemAssignment(item_name="Coke", consumed_by=["Bob"], is_shared=False),
        ],
        unclear_references=[], # Cheesecake is completely missing with 0 trace
        unmatched_mentions=[]
    )

    flags_b = cross_check_extraction_and_parsing(receipt_4items, desc_case_b)
    result_b = compute_split(receipt_4items, desc_case_b)

    print("\n[Cross-Check Flags for Case B (LOUD CATCH)]:")
    print(json.dumps(flags_b, indent=2))
    print("\n[Full Output for Case B]:")
    print(json.dumps(result_b.model_dump(by_alias=True), indent=2))

    # -------------------------------------------------------------
    # CASE C: Deliberate Hallucination — Phantom Item in Description
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print(">>> CASE C: Deliberate Hallucination — Phantom Item in Description")
    print("-" * 80)
    desc_case_c = DescriptionData(
        people=["Alice", "Bob"],
        payer="Alice",
        item_assignments=[
            ItemAssignment(item_name="Classic Burger", consumed_by=["Alice"], is_shared=False),
            ItemAssignment(item_name="French Fries", consumed_by=["Bob"], is_shared=False),
            ItemAssignment(item_name="Coke", consumed_by=["Bob"], is_shared=False),
            ItemAssignment(item_name="New York Cheesecake", consumed_by=["Alice", "Bob"], is_shared=True),
            ItemAssignment(item_name="Lobster Thermidor", consumed_by=["Alice"], is_shared=False), # Phantom!
        ],
        unclear_references=[],
        unmatched_mentions=[]
    )

    flags_c = cross_check_extraction_and_parsing(receipt_4items, desc_case_c)
    result_c = compute_split(receipt_4items, desc_case_c)

    print("\n[Cross-Check Flags for Case C (PHANTOM CATCH)]:")
    print(json.dumps(flags_c, indent=2))
    print("\n[Full Output for Case C]:")
    print(json.dumps(result_c.model_dump(by_alias=True), indent=2))


if __name__ == "__main__":
    run_cross_check_demonstration()
