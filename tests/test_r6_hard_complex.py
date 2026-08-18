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


def test_r6_hard_complex():
    print("=" * 80)
    print(" R6 HIGH-COMPLEXITY STRESS SCENARIO AUDIT")
    print(" (10 Items, Multi-Tax, 15% Discount, 10% Service Charge, 6-Person Group)")
    print("=" * 80)

    receipt = ReceiptData(
        restaurant_name="THE URBAN BREWERY & SMOKEHOUSE",
        bill_number="UB-8904",
        items=[
            ReceiptItem(name="Craft IPA Beer (Pint)", qty=3.0, unit_price=350.0, amount=1050.0),
            ReceiptItem(name="Smoked BBQ Pork Ribs", qty=1.0, unit_price=680.0, amount=680.0),
            ReceiptItem(name="Wood-Fired Truffle Pizza", qty=2.0, unit_price=540.0, amount=1080.0),
            ReceiptItem(name="Classic Caesar Salad", qty=1.0, unit_price=320.0, amount=320.0),
            ReceiptItem(name="Crispy Calamari", qty=1.0, unit_price=420.0, amount=420.0),
            ReceiptItem(name="Loaded Nachos Supreme", qty=1.0, unit_price=380.0, amount=380.0),
            ReceiptItem(name="Belgian Chocolate Lava Cake", qty=2.0, unit_price=240.0, amount=480.0),
            ReceiptItem(name="Fresh Mint Mojito", qty=2.0, unit_price=220.0, amount=440.0),
            ReceiptItem(name="Mineral Water (1L)", qty=2.0, unit_price=60.0, amount=120.0),
            ReceiptItem(name="Eco Takeaway Packaging Charge", qty=1.0, unit_price=50.0, amount=50.0),
        ],
        subtotal=5020.0,
        discount=DiscountDetail(amount=753.0, label="Zomato Gold Feast -15%"),
        service_charge=426.70,
        tax=TaxBreakdown(cgst=91.35, sgst=91.35, total_tax=331.70), # 91.35 + 91.35 + 149.00 VAT
        round_off=-0.40,
        grand_total=5025.0
    )

    desc = DescriptionData(
        people=["Vikram", "Ananya", "Kabir", "Rhea", "Siddharth", "Tara"],
        payer="Vikram",
        item_assignments=[
            ItemAssignment(item_name="Craft IPA Beer (Pint)", consumed_by=["Vikram", "Kabir"], is_shared=True),
            ItemAssignment(item_name="Fresh Mint Mojito", consumed_by=["Ananya", "Tara"], is_shared=True),
            ItemAssignment(item_name="Smoked BBQ Pork Ribs", consumed_by=["Siddharth", "Rhea"], is_shared=True),
            ItemAssignment(item_name="Crispy Calamari", consumed_by=["Siddharth", "Rhea"], is_shared=True),
            ItemAssignment(item_name="Wood-Fired Truffle Pizza", consumed_by=["Vikram", "Ananya", "Kabir", "Rhea", "Siddharth", "Tara"], is_shared=True),
            ItemAssignment(item_name="Loaded Nachos Supreme", consumed_by=["Vikram", "Ananya", "Kabir", "Rhea", "Siddharth", "Tara"], is_shared=True),
            ItemAssignment(item_name="Mineral Water (1L)", consumed_by=["Vikram", "Ananya", "Kabir", "Rhea", "Siddharth", "Tara"], is_shared=True),
            ItemAssignment(item_name="Classic Caesar Salad", consumed_by=["Ananya"], is_shared=False),
            ItemAssignment(item_name="Belgian Chocolate Lava Cake", consumed_by=["Rhea", "Tara", "Vikram"], is_shared=True),
            # Eco Takeaway Packaging Charge intentionally not mentioned -> defaults to shared with quality flag
        ]
    )

    result = compute_split(receipt, desc)
    print("\n[R6 Output JSON]:")
    print(json.dumps(result.model_dump(by_alias=True), indent=2))

    # Assertions
    assert result.reconciliation.matches_bill is True, "Reconciliation failed on R6!"
    assert result.reconciliation.sum_of_person_totals == 5025.0, f"Sum ({result.reconciliation.sum_of_person_totals}) != 5025.0"
    assert len(result.per_person) == 6
    assert result.paid_by == "Vikram"
    assert len(result.settle_up) == 5
    assert any("Eco Takeaway Packaging Charge" in r for r in result.confidence.reasons)

    print("\n--> Verification: Sum of Person Totals =", result.reconciliation.sum_of_person_totals, "= Grand Total 5025.0")
    print("--> Settle-Up Transactions Count =", len(result.settle_up), "(5 non-payers reimburse Vikram)")
    print("\n>>> PASS: R6 High-Complexity Stress Scenario executed and reconciled perfectly!")


if __name__ == "__main__":
    test_r6_hard_complex()
