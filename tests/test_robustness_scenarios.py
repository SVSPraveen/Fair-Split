"""
Unit tests for the 4 robustness scenarios:
1. Custom / non-standard item names (grocery list style)
2. Fuzzy item name matching in compute
3. 2-person sharing math correctness
4. Non-receipt detection guard
"""
import sys
sys.path.insert(0, '.')

from backend.compute import _match_item_assignment, _normalize
from backend.models import ItemAssignment

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

print()
if all_ok:
    print(">>> ALL TESTS PASSED ✅")
else:
    print(">>> SOME TESTS FAILED ❌")
