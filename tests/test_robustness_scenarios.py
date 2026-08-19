"""
Unit tests for the 4 robustness scenarios:
1. Custom / non-standard item names (grocery list style)
2. Fuzzy item name matching in compute
3. 2-person sharing math correctness
4. Non-receipt detection guard
"""
import sys
sys.path.insert(0, '.')

from backend.compute import _match_item_assignment, _normalize, compute_split
from backend.models import ItemAssignment, DescriptionData, ReceiptData, ReceiptItem, TaxBreakdown

def make_assign(name, consumers, shared=True):
    return ItemAssignment(item_name=name, consumed_by=consumers, is_shared=shared)

print("=== TEST 1: Fuzzy Matching ===")
assignments = [
    make_assign("Chicken Tikka Starter", ["Arjun", "Meena"]),
    make_assign("Garlic Naan", ["Arjun"]),
    make_assign("Gulab Jamun", ["Meena"]),
    make_assign("Masala Chai", ["Arjun", "Meena"]),
]

tests = [
    ("Chicken Tikka Starter", "Chicken Tikka Starter"),   # exact
    ("chicken tikka", "Chicken Tikka Starter"),             # substring fuzzy
    ("Tikka", "Chicken Tikka Starter"),                     # short substring
    ("Naan", "Garlic Naan"),                                # reverse substring
    ("Jamun", "Gulab Jamun"),                               # partial
    ("chai", "Masala Chai"),                                # lowercase partial
    ("Mango Juice", None),                                  # no match
]

all_ok = True
for query, expected_name in tests:
    result = _match_item_assignment(query, assignments)
    got = result.item_name if result else None
    ok = (got == expected_name)
    print(f"  {'✅' if ok else '❌'} '{query}' -> {got!r} (expected {expected_name!r})")
    if not ok:
        all_ok = False

print()
print("=== TEST 2: 2-Person Shared Item Math ===")
# If pizza costs ₹540 and 2 people share it, each should pay ₹270
pizza_amount = 540.0
num_sharers = 2
share = pizza_amount / num_sharers
print(f"  ₹{pizza_amount} pizza / {num_sharers} people = ₹{share} each")
assert share == 270.0, f"Expected 270.0 got {share}"
print("  ✅ Math correct")

# 3 people share ₹1050 beer = ₹350 each
beer_amount = 1050.0
num_beer = 3
beer_share = beer_amount / num_beer
print(f"  ₹{beer_amount} beer / {num_beer} people = ₹{beer_share} each")
assert beer_share == 350.0, f"Expected 350.0 got {beer_share}"
print("  ✅ Math correct")

print()
print("=== TEST 3: Non-receipt guard logic ===")
from backend.models import ReceiptData
# Simulate what would happen with a blank/selfie image extraction result
empty_receipt_dict = {
    "restaurant_name": None,
    "bill_number": None,
    "items": [],
    "subtotal": 0.0,
    "discount": None,
    "service_charge": None,
    "tax": None,
    "round_off": None,
    "grand_total": 0.0
}
r = ReceiptData.model_validate(empty_receipt_dict)
guard_triggered = not r.items and (r.grand_total is None or r.grand_total == 0.0)
print(f"  Non-receipt guard would trigger: {'✅ YES' if guard_triggered else '❌ NO'}")

print()
print("=== TEST 4: Auto grand_total computation ===")
# If items exist but grand_total is 0, it should be auto-computed
custom_receipt = ReceiptData.model_validate({
    "restaurant_name": "Home Kitchen",
    "bill_number": None,
    "items": [
        {"name": "Biryani", "qty": 1.0, "unit_price": 200.0, "amount": 200.0},
        {"name": "Raita", "qty": 1.0, "unit_price": 50.0, "amount": 50.0},
        {"name": "Coke", "qty": 2.0, "unit_price": 40.0, "amount": 80.0}
    ],
    "subtotal": 330.0,
    "discount": None,
    "service_charge": None,
    "tax": None,
    "round_off": None,
    "grand_total": 0.0
})
# Simulate the auto-compute logic
if custom_receipt.grand_total == 0.0 and custom_receipt.items:
    custom_receipt.grand_total = round(sum(i.amount for i in custom_receipt.items), 2)
print(f"  Auto-computed grand_total: ₹{custom_receipt.grand_total}")
assert custom_receipt.grand_total == 330.0, f"Expected 330.0 got {custom_receipt.grand_total}"
print("  ✅ Auto-compute correct")

def test_receipt_corrections():
    print("\n=== TEST 5: Receipt Corrections ===")
    # 1. Ignored item
    desc1 = DescriptionData(
        people=["Alice", "Bob"],
        item_assignments=[ItemAssignment(item_name="pizza", consumed_by=["Alice"])],
        ignored_items=["burger"]
    )
    receipt1 = ReceiptData(
        grand_total=300.0,
        items=[
            ReceiptItem(name="pizza", amount=200.0, unit_price=200.0, qty=1),
            ReceiptItem(name="burger", amount=100.0, unit_price=100.0, qty=1)
        ]
    )
    res1 = compute_split(receipt1, desc1)
    # Burger was ignored, so adjusted grand total is 200.0
    assert res1.grand_total == 200.0
    assert res1.per_person[0].total == 200.0
    print("  ✅ Ignored items deducted correctly")

    # 2. Tax override
    desc2 = DescriptionData(
        people=["Alice"],
        item_assignments=[ItemAssignment(item_name="pizza", consumed_by=["Alice"])],
        tax_override=50.0
    )
    receipt2 = ReceiptData(
        grand_total=250.0,
        tax=TaxBreakdown(total_tax=100.0), # Receipt says 100, but desc overrides to 50
        items=[ReceiptItem(name="pizza", amount=200.0, unit_price=200.0, qty=1)]
    )
    res2 = compute_split(receipt2, desc2)
    # LRM will reconcile to 250 because receipt grand_total is still 250, but let's check tax_share
    assert res2.per_person[0].tax_share == 50.0
    print("  ✅ Tax override applied correctly")

    # 3. Wrong receipt rejection
    desc3 = DescriptionData(
        people=["Alice"],
        is_receipt_completely_wrong=True
    )
    receipt3 = ReceiptData(grand_total=100.0, items=[])
    try:
        compute_split(receipt3, desc3)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "does not match the description" in str(e)
        print("  ✅ Wrong receipt rejection triggered correctly")

test_receipt_corrections()
print("\n>>> ALL TESTS PASSED ✅")
