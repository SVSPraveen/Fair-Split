# Edge Cases & Stress-Test Documentation

This document logs all 11 edge cases (Cases 1–10 plus the Case 4b variant) executed through the Fair-Split pipeline ([`tests/test_edge_cases.py`](file:///e:/Epifi%20Technologies/tests/test_edge_cases.py)), detailing the exact input, system behavior, verification status, and honest verdict.

---

### Case 1: No Service Charge on Bill

- **Input**:
  - *Receipt*: "The Burger Shack" — Classic Burger (₹250.00), Cold Coffee (₹150.00). Subtotal: ₹400.00. Service Charge: `null`. CGST: ₹10.00, SGST: ₹10.00. Grand Total: ₹420.00.
  - *Description*: `"Alice and Bob. Alice had the Classic Burger, Bob had the Cold Coffee. Alice paid."`
- **System Behavior**:
  - The extraction schema accepted `service_charge: null`.
  - The compute engine safely evaluated `total_service = 0.0` without encountering `TypeError` or division-by-zero errors.
  - Proportional tax allocated: Alice ₹12.50, Bob ₹7.50. Alice total = ₹262.00, Bob total = ₹158.00. Settle-up: Bob pays Alice ₹158.00.
- **Verification Status**: Verified with live API execution in `test_edge_cases.py`.
- **Verdict**: **Handled correctly**

---

### Case 2: Printed Total Arithmetic Discrepancy

- **Input**:
  - *Receipt*: "Pasta Villa" — Arrabiata Pasta (₹300.00), Fresh Lemonade (₹100.00). Subtotal: ₹400.00, Service: ₹20.00, CGST: ₹10.00, SGST: ₹10.00 *(Expected Total = ₹440.00)*. Printed Grand Total: **₹500.00** *(an intentional ₹60 unbilled gap)*.
  - *Description*: `"Pooja and Varun. Pooja had the Arrabiata Pasta, Varun had the Fresh Lemonade. Pooja paid."`
- **System Behavior**:
  - The extraction module's self-check caught the disparity and attached `"Grand total mismatch: computed expected (440.00) != printed grand total (500.00)"` to `extraction_flags`.
  - The flag was preserved through the API response into `flags`.
  - The compute engine assigned the ₹60 unaccounted difference to Pooja (the payer) and logged: `"Rounding discrepancy of ₹+60.00 absorbed by payer (Pooja) to match bill grand total ₹500.00 exactly."`.
- **Verification Status**: Verified with live API execution in `test_edge_cases.py`.
- **Verdict**: **Flagged appropriately**

---

### Case 3: Description Mentions Unbilled Item ("Cheesecake")

- **Input**:
  - *Receipt*: "Cafe Mocha" — Cappuccino (₹180.00), Butter Croissant (₹140.00). Subtotal: ₹320.00, Tax: ₹16.00, Grand Total: ₹336.00.
  - *Description*: `"Rahul and Priya. Rahul had the cappuccino, Priya had the butter croissant and also ordered a blueberry cheesecake. Rahul paid."`
- **System Behavior**:
  - The description parser cross-referenced the text against `known_items` (`['Cappuccino', 'Butter Croissant']`).
  - It recognized "blueberry cheesecake" was absent from the receipt and placed it into `unmatched_mentions: ["blueberry cheesecake"]`.
  - The API surfaced this in `flags: ["Unmatched mention from description: 'blueberry cheesecake'"]` without dropping it or fuzzy-matching it to existing items.
- **Verification Status**: Verified with live API execution in `test_edge_cases.py`.
- **Verdict**: **Flagged appropriately**

---

### Case 4: Ambiguous "The Rest of Us" (2 Unassigned People)

- **Input**:
  - *Receipt*: "Bistro Five" — Ribeye Steak (₹600.00), Pepperoni Pizza (₹400.00), Veg Burger (₹300.00), Chocolate Fondant (₹200.00). Grand Total: ₹1650.00.
  - *Description*: `"Five of us: Alex, Ben, Charlie, Dave, Ethan. Alex had the Ribeye Steak, Ben had the Pepperoni Pizza, Charlie had the Veg Burger. The rest of us shared the Chocolate Fondant. Dave paid."`
- **System Behavior**:
  - With Alex, Ben, and Charlie assigned individual mains, exactly 2 people (Dave & Ethan) were unassigned.
  - The model resolved "the rest of us" by elimination to Dave & Ethan, splitting the ₹200.00 fondant 50/50 (₹100.00 each).
  - Explicit assumption logged: `"'rest of us' was interpreted as the remaining group members Dave and Ethan."`.
- **Verification Status**: Verified with live API execution in `test_edge_cases.py`.
- **Verdict**: **Handled correctly** *(weak test of ambiguity due to exact 2-person elimination)*

---

### Case 4b: Genuine Ambiguity (3 Unassigned People with "The Rest of Us")

- **Input**:
  - *Receipt*: "Bistro Five" — Ribeye Steak (₹600.00), Pepperoni Pizza (₹400.00), Chocolate Fondant (₹300.00). Grand Total: ₹1430.00.
  - *Description*: `"Five of us: Alex, Ben, Charlie, Dave, Ethan. Alex had the Ribeye Steak, Ben had the Pepperoni Pizza. The rest of us shared the Chocolate Fondant. Dave paid."` *(3 people unassigned: Charlie, Dave, Ethan)*.
- **System Behavior**:
  - Rather than guessing an arbitrary 2-person subset among the 3, the language model assigned the Chocolate Fondant equally across all 3 remaining unassigned diners (Charlie ₹100, Dave ₹100, Ethan ₹100).
  - Explicit assumption logged: `"'the rest of us' was interpreted as the remaining named individuals (Charlie, Dave, Ethan)."`.
- **Verification Status**: Verified with live API execution in `test_edge_cases.py`.
- **Verdict**: **Handled correctly**

---

### Case 5: Partial Subset Sharing (3 of 5 People)

- **Input**:
  - *Receipt*: "Metro Diner" — Large Nachos (₹450.00), Caesar Salad (₹200.00), Chicken Wings (₹300.00), Mint Lemonade (₹120.00), Iced Tea (₹100.00). Grand Total: ₹1287.00.
  - *Description*: `"Five people: Aryan, Bhavya, Chirag, Divya, Esha. Large Nachos was shared only by Aryan, Bhavya, and Chirag. Divya had the Caesar Salad, Esha had the Chicken Wings. Aryan had the Mint Lemonade, Bhavya had the Iced Tea. Divya paid."`
- **System Behavior**:
  - Large Nachos split 3 ways (₹150.00 each to Aryan, Bhavya, Chirag; ₹0.00 to Divya and Esha).
  - Individual subtotals: Aryan ₹270, Bhavya ₹250, Chirag ₹150, Divya ₹200, Esha ₹300.
  - Taxes and service charge distributed strictly in proportion to these distinct subtotals.
  - Settle-up generated 4 transfers to Divya totaling ₹1067.00 (reconciling exactly to Divya's total of ₹220.00 out of ₹1287.00).
- **Verification Status**: Verified with live API execution in `test_edge_cases.py`.
- **Verdict**: **Handled correctly**

---

### Case 6: Non-Even Division & Repeating Fractions

- **Input**:
  - *Receipt*: "The Taproom" — Craft Beer Pitcher (qty 2 @ ₹175 = ₹350.00). Subtotal: ₹350.00, Tax: ₹17.50, Round-off: +₹0.50, Grand Total: **₹368.00**.
  - *Description*: `"Three of us: Jack, Liam, Noah. The craft beer pitcher was shared equally by all three of us. Jack paid."`
- **System Behavior**:
  - Pre-tax subtotal = ₹116.666... per person. Tax share = ₹5.833... per person.
  - Raw unrounded individual total = ₹122.50 each.
  - Independent rounding produced ₹123, ₹123, ₹123 (sum = ₹369.00).
  - Leftover rounding discrepancy ($\text{diff} = 368 - 369 = -1$) was absorbed by Jack (the payer), adjusting Jack's total to ₹122.00.
  - Liam pays Jack ₹123.00, Noah pays Jack ₹123.00. Sum of totals = ₹368.00.
- **Verification Status**: Verified with live API execution in `test_edge_cases.py`.
- **Verdict**: **Handled correctly**

---

### Case 7: Unmodeled Fee ("Container & Packaging Charge")

- **Input**:
  - *Receipt*: "Biryani Express" — Hyderabadi Biryani (₹350.00), Mirchi Salan (₹100.00), Container & Packaging Charge (₹40.00). Grand Total: ₹514.00.
  - *Description*: `"Karan and Kabir. Karan had the Hyderabadi Biryani, Kabir had the Mirchi Salan. Karan paid."`
- **System Behavior**:
  - The vision OCR model extracted "Container & Packaging Charge" as a standard line item in `items`.
  - Because neither diner claimed it, the compute engine defaulted it to shared equally across both people (₹20.00 to Karan, ₹20.00 to Kabir) and raised the flag: `"Item 'Container & Packaging Charge' was not explicitly assigned; defaulted to shared by all 2 people."`.
  - The fee was incorporated into the pre-tax food subtotal and taxed proportionally like food.
- **Verification Status**: Verified with live API execution in `test_edge_cases.py`.
- **Verdict**: **No rule covers non-food charges; this system's choice was to fold them into subtotal and tax them like food — this is a design decision requiring documentation, not a verified-correct behavior.**

---

### Case 8: Multiple People Owing Identical Amounts

- **Input**:
  - *Receipt*: "Taco Bell" — Burrito Meal (₹300.00), Quesadilla Meal (₹300.00), Taco Meal (₹300.00). Grand Total: ₹945.00.
  - *Description*: `"Three people: Maya, Nidhi, Ojas. Maya had the Burrito Meal, Nidhi had the Quesadilla Meal, Ojas had the Taco Meal. Ojas paid."`
- **System Behavior**:
  - Maya and Nidhi each incurred an identical total of ₹315.00.
  - The settle-up generator created two distinct transfers: `{"from": "Maya", "to": "Ojas", "amount": 315.0}` and `{"from": "Nidhi", "to": "Ojas", "amount": 315.0}` without collision or deduplication.
- **Verification Status**: Verified with live API execution in `test_edge_cases.py`.
- **Verdict**: **Handled correctly**

---

### Case 9: No Payer Stated in Description

- **Input**:
  - *Receipt*: "Green Leaf Cafe" — Greek Salad (₹250.00), Mushroom Soup (₹200.00). Grand Total: ₹473.00.
  - *Description*: `"Two of us: Sid and Tina. Sid had the Greek Salad, Tina had the Mushroom Soup."`
- **System Behavior**:
  - Description parser set `payer: null`.
  - Compute engine returned `paid_by: null`, `settle_up: []`, and attached `"Payer not specified in description. Settle-up transactions cannot be computed."` to `flags`.
- **Verification Status**: Verified with live API execution in `test_edge_cases.py`.
- **Verdict**: **Flagged appropriately**

---

### Case 10: Zero-Consumption Party Member (Kavita)

- **Input**:
  - *Receipt*: "Tea Lounge" — Masala Chai (₹120.00), Bun Maska (₹100.00). Grand Total: ₹231.00.
  - *Description*: `"Three of us: Rohan, Sneha, Kavita. Rohan had the Masala Chai, Sneha had the Bun Maska. Kavita joined us for company but didn't eat or drink anything. Rohan paid."`
- **System Behavior**:
  - Kavita was recognized as a group member and explicitly retained in `per_person`:
    `{"name": "Kavita", "items": [], "subtotal": 0.0, "tax_share": 0.0, "service_share": 0.0, "discount_share": 0.0, "total": 0.0}`.
  - Kavita was excluded from `settle_up` because her payable total was ₹0.00.
  - Rohan and Sneha absorbed 100% of the proportional taxes according to their consumption (Rohan ₹126.00, Sneha ₹105.00).
- **Verification Status**: Verified with live API execution in `test_edge_cases.py`.
- **Verdict**: **Handled correctly**

---

### Case 11: High-Complexity Stress Feast (10 Items, Multi-Tax, 15% Discount, 10% Service Charge, 6-Person Group)

- **Input**:
  - *Receipt*: "The Urban Brewery & Smokehouse" (R6 sample receipt) — 10 line items including Craft IPA Beer (₹1050), Smoked BBQ Ribs (₹680), Truffle Pizza (₹1080), Caesar Salad (₹320), Calamari (₹420), Nachos (₹380), Lava Cake (₹480), Mojitos (₹440), Water (₹120), Packaging (₹50). Subtotal: ₹5020.00. Discount (15% Gold): -₹753.00. Service Charge (10%): ₹426.70. Multi-Tax (CGST 2.5% + SGST 2.5% + Liquor VAT 10%): ₹331.70. Round Off: -₹0.40. Grand Total: ₹5025.00.
  - *Description*: `"Party of six: Vikram, Ananya, Kabir, Rhea, Siddharth, Tara. Vikram and Kabir shared the 3 pints of Craft IPA Beer. Ananya and Tara had the Fresh Mint Mojitos. Siddharth and Rhea shared the Smoked BBQ Pork Ribs and Crispy Calamari. All six of us shared the 2 Wood-Fired Truffle Pizzas, Loaded Nachos Supreme, and Mineral Water. Ananya had the Classic Caesar Salad. Rhea, Tara, and Vikram shared the 2 Belgian Chocolate Lava Cakes. Vikram paid the entire bill."`
- **System Behavior**:
  - Successfully mapped 9 dish assignments across overlapping subgroups (pairs, trios, and full 6-person group).
  - Detected that `Eco Takeaway Packaging Charge` was unassigned; cross-check defaulted it to shared across all 6 members and flagged `needs_review`.
  - Applied proportional pre-tax subtotal shares for 15% bill discount, 10% service charge, and composite multi-tax rates.
  - Nearest rupee rounding produced ₹1.00 discrepancy, which was absorbed by the payer (Vikram) via Rule 5.
  - Sum of person totals equaled ₹5025.00 (matching printed grand total ₹5025.00).
  - Generated 5 distinct direct-to-payer settle-up reimbursements from Ananya (₹812), Kabir (₹797), Rhea (₹983), Siddharth (₹822), and Tara (₹652) to Vikram.
- **Verification Status**: Verified with live execution in `test_r6_hard_complex.py` and `test_edge_cases.py`.
- **Verdict**: **Handled correctly**

