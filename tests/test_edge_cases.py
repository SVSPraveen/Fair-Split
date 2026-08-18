import io
import sys
import json
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont

# Ensure UTF-8 output handling in Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def generate_mock_receipt_bytes(
    restaurant_name: str,
    bill_number: str,
    items: List[Dict[str, Any]],
    subtotal: float,
    discount_label: Optional[str] = None,
    discount_amount: Optional[float] = None,
    service_charge: Optional[float] = None,
    cgst: Optional[float] = None,
    sgst: Optional[float] = None,
    round_off: Optional[float] = None,
    grand_total: float = 0.0,
    custom_charges: Optional[List[Dict[str, Any]]] = None
) -> bytes:
    """Renders a clean receipt image into PNG bytes for edge-case testing."""
    width, height = 550, 750
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font_header = ImageFont.truetype("arial.ttf", 22)
        font_sub = ImageFont.truetype("arial.ttf", 13)
        font_bold = ImageFont.truetype("arialbd.ttf", 14)
        font_regular = ImageFont.truetype("arial.ttf", 13)
    except IOError:
        font_header = ImageFont.load_default()
        font_sub = font_header
        font_bold = font_header
        font_regular = font_header

    y = 25
    draw.text((width // 2, y), restaurant_name.upper(), fill=(0, 0, 0), font=font_header, anchor="mt")
    y += 30
    draw.text((width // 2, y), f"TAX INVOICE / BILL #{bill_number}", fill=(80, 80, 80), font=font_sub, anchor="mt")
    y += 25
    draw.line([(30, y), (width - 30, y)], fill=(180, 180, 180), width=1)
    y += 15

    # Table Header
    draw.text((35, y), "ITEM", fill=(0, 0, 0), font=font_bold)
    draw.text((280, y), "QTY", fill=(0, 0, 0), font=font_bold, anchor="mt")
    draw.text((360, y), "PRICE", fill=(0, 0, 0), font=font_bold, anchor="mt")
    draw.text((width - 35, y), "AMOUNT", fill=(0, 0, 0), font=font_bold, anchor="rt")
    y += 20
    draw.line([(30, y), (width - 30, y)], fill=(200, 200, 200), width=1)
    y += 12

    for it in items:
        name = it["name"]
        qty = it["qty"]
        price = it["unit_price"]
        amount = it["amount"]
        draw.text((35, y), name, fill=(20, 20, 20), font=font_regular)
        draw.text((280, y), str(qty), fill=(20, 20, 20), font=font_regular, anchor="mt")
        draw.text((360, y), f"{price:.2f}", fill=(20, 20, 20), font=font_regular, anchor="mt")
        draw.text((width - 35, y), f"{amount:.2f}", fill=(20, 20, 20), font=font_regular, anchor="rt")
        y += 22

    if custom_charges:
        for c in custom_charges:
            draw.text((35, y), c["name"], fill=(20, 20, 20), font=font_regular)
            draw.text((width - 35, y), f"{c['amount']:.2f}", fill=(20, 20, 20), font=font_regular, anchor="rt")
            y += 22

    y += 10
    draw.line([(30, y), (width - 30, y)], fill=(180, 180, 180), width=1)
    y += 15

    # Subtotal
    draw.text((35, y), "Subtotal:", fill=(50, 50, 50), font=font_regular)
    draw.text((width - 35, y), f"Rs. {subtotal:.2f}", fill=(0, 0, 0), font=font_bold, anchor="rt")
    y += 20

    if discount_amount:
        label = discount_label or "Discount"
        draw.text((35, y), f"Discount ({label}):", fill=(180, 0, 0), font=font_regular)
        draw.text((width - 35, y), f"-Rs. {discount_amount:.2f}", fill=(180, 0, 0), font=font_bold, anchor="rt")
        y += 20

    if service_charge is not None and service_charge > 0:
        draw.text((35, y), "Service Charge (5%):", fill=(50, 50, 50), font=font_regular)
        draw.text((width - 35, y), f"Rs. {service_charge:.2f}", fill=(0, 0, 0), font=font_regular, anchor="rt")
        y += 20

    if cgst is not None and sgst is not None:
        draw.text((35, y), "CGST (2.5%):", fill=(50, 50, 50), font=font_regular)
        draw.text((width - 35, y), f"Rs. {cgst:.2f}", fill=(0, 0, 0), font=font_regular, anchor="rt")
        y += 20
        draw.text((35, y), "SGST (2.5%):", fill=(50, 50, 50), font=font_regular)
        draw.text((width - 35, y), f"Rs. {sgst:.2f}", fill=(0, 0, 0), font=font_regular, anchor="rt")
        y += 20

    if round_off is not None:
        sign = "+" if round_off >= 0 else "-"
        draw.text((35, y), "Round Off:", fill=(50, 50, 50), font=font_regular)
        draw.text((width - 35, y), f"{sign}Rs. {abs(round_off):.2f}", fill=(50, 50, 50), font=font_regular, anchor="rt")
        y += 20

    y += 10
    draw.line([(30, y), (width - 30, y)], fill=(0, 0, 0), width=2)
    y += 15

    # Grand Total
    draw.text((35, y), "GRAND TOTAL:", fill=(0, 0, 0), font=font_header)
    draw.text((width - 35, y), f"Rs. {grand_total:.2f}", fill=(0, 0, 0), font=font_header, anchor="rt")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def run_pipeline(image_bytes: bytes, description: str) -> Dict[str, Any]:
    """Helper to run image bytes and description through the live FastAPI endpoint."""
    b64_str = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "receipt_base64": b64_str,
        "description": description
    }
    response = client.post("/split", json=payload)
    if response.status_code != 200:
        return {
            "_http_status": response.status_code,
            "_error": response.json()
        }
    return response.json()


def run_all_edge_case_tests():
    print("\n" + "=" * 70)
    print(" FAIR-SPLIT STRESS-TEST & EDGE-CASE SUITE (10 TEST CASES)")
    print("=" * 70 + "\n")

    results = {}

    # -------------------------------------------------------------
    # CASE 1: No service charge on the bill
    # -------------------------------------------------------------
    print(">>> Running Case 1: No Service Charge on Bill...")
    img1 = generate_mock_receipt_bytes(
        restaurant_name="The Burger Shack",
        bill_number="EDGE-01",
        items=[
            {"name": "Classic Burger", "qty": 1, "unit_price": 250.0, "amount": 250.0},
            {"name": "Cold Coffee", "qty": 1, "unit_price": 150.0, "amount": 150.0}
        ],
        subtotal=400.0,
        service_charge=None,
        cgst=10.0,
        sgst=10.0,
        round_off=0.0,
        grand_total=420.0
    )
    desc1 = "Alice and Bob. Alice had the Classic Burger, Bob had the Cold Coffee. Alice paid."
    res1 = run_pipeline(img1, desc1)
    results["Case 1"] = res1

    # -------------------------------------------------------------
    # CASE 2: Printed total doesn't reconcile with line items
    # -------------------------------------------------------------
    print(">>> Running Case 2: Printed Total Discrepancy (Printed Grand Total Off by ₹60)...")
    # Subtotal 400 + Service 20 + Tax 20 = 440, but printed grand total is 500.00
    img2 = generate_mock_receipt_bytes(
        restaurant_name="Pasta Villa",
        bill_number="EDGE-02",
        items=[
            {"name": "Arrabiata Pasta", "qty": 1, "unit_price": 300.0, "amount": 300.0},
            {"name": "Fresh Lemonade", "qty": 1, "unit_price": 100.0, "amount": 100.0}
        ],
        subtotal=400.0,
        service_charge=20.0,
        cgst=10.0,
        sgst=10.0,
        round_off=0.0,
        grand_total=500.0  # Intentional ₹60 mismatch
    )
    desc2 = "Pooja and Varun. Pooja had the Arrabiata Pasta, Varun had the Fresh Lemonade. Pooja paid."
    res2 = run_pipeline(img2, desc2)
    results["Case 2"] = res2

    # -------------------------------------------------------------
    # CASE 3: Description mentions an item not on the receipt
    # -------------------------------------------------------------
    print(">>> Running Case 3: Description Mentions Unbilled Item (Cheesecake)...")
    img3 = generate_mock_receipt_bytes(
        restaurant_name="Cafe Mocha",
        bill_number="EDGE-03",
        items=[
            {"name": "Cappuccino", "qty": 1, "unit_price": 180.0, "amount": 180.0},
            {"name": "Butter Croissant", "qty": 1, "unit_price": 140.0, "amount": 140.0}
        ],
        subtotal=320.0,
        cgst=8.0,
        sgst=8.0,
        round_off=0.0,
        grand_total=336.0
    )
    desc3 = "Rahul and Priya. Rahul had the cappuccino, Priya had the butter croissant and also ordered a blueberry cheesecake. Rahul paid."
    res3 = run_pipeline(img3, desc3)
    results["Case 3"] = res3

    # -------------------------------------------------------------
    # CASE 4: Ambiguous 'the rest of us' / 'everyone else' (2 unassigned)
    # -------------------------------------------------------------
    print(">>> Running Case 4: Ambiguous 'The Rest of Us' with 5 People (2 Unassigned)...")
    img4 = generate_mock_receipt_bytes(
        restaurant_name="Bistro Five",
        bill_number="EDGE-04",
        items=[
            {"name": "Ribeye Steak", "qty": 1, "unit_price": 600.0, "amount": 600.0},
            {"name": "Pepperoni Pizza", "qty": 1, "unit_price": 400.0, "amount": 400.0},
            {"name": "Veg Burger", "qty": 1, "unit_price": 300.0, "amount": 300.0},
            {"name": "Chocolate Fondant", "qty": 1, "unit_price": 200.0, "amount": 200.0}
        ],
        subtotal=1500.0,
        service_charge=75.0,
        cgst=37.5,
        sgst=37.5,
        round_off=0.0,
        grand_total=1650.0
    )
    desc4 = "Five of us: Alex, Ben, Charlie, Dave, Ethan. Alex had the Ribeye Steak, Ben had the Pepperoni Pizza, Charlie had the Veg Burger. The rest of us shared the Chocolate Fondant. Dave paid."
    res4 = run_pipeline(img4, desc4)
    results["Case 4"] = res4

    # -------------------------------------------------------------
    # CASE 4b: Genuine Ambiguity (3 Unassigned People with 'the rest of us')
    # -------------------------------------------------------------
    print(">>> Running Case 4b: Genuine Ambiguity with 3 Unassigned People ('the rest of us')...")
    img4b = generate_mock_receipt_bytes(
        restaurant_name="Bistro Five",
        bill_number="EDGE-04B",
        items=[
            {"name": "Ribeye Steak", "qty": 1, "unit_price": 600.0, "amount": 600.0},
            {"name": "Pepperoni Pizza", "qty": 1, "unit_price": 400.0, "amount": 400.0},
            {"name": "Chocolate Fondant", "qty": 1, "unit_price": 300.0, "amount": 300.0}
        ],
        subtotal=1300.0,
        service_charge=65.0,
        cgst=32.5,
        sgst=32.5,
        round_off=0.0,
        grand_total=1430.0
    )
    desc4b = "Five of us: Alex, Ben, Charlie, Dave, Ethan. Alex had the Ribeye Steak, Ben had the Pepperoni Pizza. The rest of us shared the Chocolate Fondant. Dave paid."
    res4b = run_pipeline(img4b, desc4b)
    results["Case 4b"] = res4b


    # -------------------------------------------------------------
    # CASE 5: Shared item across an unusual subset (3 of 5 people)
    # -------------------------------------------------------------
    print(">>> Running Case 5: Subset Sharing (3 of 5 People)...")
    img5 = generate_mock_receipt_bytes(
        restaurant_name="Metro Diner",
        bill_number="EDGE-05",
        items=[
            {"name": "Large Nachos", "qty": 1, "unit_price": 450.0, "amount": 450.0},
            {"name": "Caesar Salad", "qty": 1, "unit_price": 200.0, "amount": 200.0},
            {"name": "Chicken Wings", "qty": 1, "unit_price": 300.0, "amount": 300.0},
            {"name": "Mint Lemonade", "qty": 1, "unit_price": 120.0, "amount": 120.0},
            {"name": "Iced Tea", "qty": 1, "unit_price": 100.0, "amount": 100.0}
        ],
        subtotal=1170.0,
        service_charge=58.5,
        cgst=29.25,
        sgst=29.25,
        round_off=0.0,
        grand_total=1287.0
    )
    desc5 = "Five people: Aryan, Bhavya, Chirag, Divya, Esha. Large Nachos was shared only by Aryan, Bhavya, and Chirag. Divya had the Caesar Salad, Esha had the Chicken Wings. Aryan had the Mint Lemonade, Bhavya had the Iced Tea. Divya paid."
    res5 = run_pipeline(img5, desc5)
    results["Case 5"] = res5

    # -------------------------------------------------------------
    # CASE 6: Non-even division & repeating fractions
    # -------------------------------------------------------------
    print(">>> Running Case 6: Fractional Division (₹350 split 3 ways)...")
    img6 = generate_mock_receipt_bytes(
        restaurant_name="The Taproom",
        bill_number="EDGE-06",
        items=[
            {"name": "Craft Beer Pitcher", "qty": 2, "unit_price": 175.0, "amount": 350.0}
        ],
        subtotal=350.0,
        cgst=8.75,
        sgst=8.75,
        round_off=0.50,
        grand_total=368.0
    )
    desc6 = "Three of us: Jack, Liam, Noah. The craft beer pitcher was shared equally by all three of us. Jack paid."
    res6 = run_pipeline(img6, desc6)
    results["Case 6"] = res6

    # -------------------------------------------------------------
    # CASE 7: Unmodeled fee ("Container & Packaging Charge")
    # -------------------------------------------------------------
    print(">>> Running Case 7: Unmodeled Charge (Packaging Charge)...")
    img7 = generate_mock_receipt_bytes(
        restaurant_name="Biryani Express",
        bill_number="EDGE-07",
        items=[
            {"name": "Hyderabadi Biryani", "qty": 1, "unit_price": 350.0, "amount": 350.0},
            {"name": "Mirchi Salan", "qty": 1, "unit_price": 100.0, "amount": 100.0}
        ],
        custom_charges=[
            {"name": "Container & Packaging Charge", "amount": 40.0}
        ],
        subtotal=490.0,
        cgst=12.25,
        sgst=12.25,
        round_off=-0.50,
        grand_total=514.0
    )
    desc7 = "Karan and Kabir. Karan had the Hyderabadi Biryani, Kabir had the Mirchi Salan. Karan paid."
    res7 = run_pipeline(img7, desc7)
    results["Case 7"] = res7

    # -------------------------------------------------------------
    # CASE 8: Multiple people owing identical amounts
    # -------------------------------------------------------------
    print(">>> Running Case 8: Equal Settle-Up Debts...")
    img8 = generate_mock_receipt_bytes(
        restaurant_name="Taco Bell",
        bill_number="EDGE-08",
        items=[
            {"name": "Burrito Meal", "qty": 1, "unit_price": 300.0, "amount": 300.0},
            {"name": "Quesadilla Meal", "qty": 1, "unit_price": 300.0, "amount": 300.0},
            {"name": "Taco Meal", "qty": 1, "unit_price": 300.0, "amount": 300.0}
        ],
        subtotal=900.0,
        cgst=22.5,
        sgst=22.5,
        round_off=0.0,
        grand_total=945.0
    )
    desc8 = "Three people: Maya, Nidhi, Ojas. Maya had the Burrito Meal, Nidhi had the Quesadilla Meal, Ojas had the Taco Meal. Ojas paid."
    res8 = run_pipeline(img8, desc8)
    results["Case 8"] = res8

    # -------------------------------------------------------------
    # CASE 9: No payer stated in description
    # -------------------------------------------------------------
    print(">>> Running Case 9: No Payer Stated...")
    img9 = generate_mock_receipt_bytes(
        restaurant_name="Green Leaf Cafe",
        bill_number="EDGE-09",
        items=[
            {"name": "Greek Salad", "qty": 1, "unit_price": 250.0, "amount": 250.0},
            {"name": "Mushroom Soup", "qty": 1, "unit_price": 200.0, "amount": 200.0}
        ],
        subtotal=450.0,
        cgst=11.25,
        sgst=11.25,
        round_off=0.50,
        grand_total=473.0
    )
    desc9 = "Two of us: Sid and Tina. Sid had the Greek Salad, Tina had the Mushroom Soup."
    res9 = run_pipeline(img9, desc9)
    results["Case 9"] = res9

    # -------------------------------------------------------------
    # CASE 10: Zero-Consumption Party Member (Kavita)
    # -------------------------------------------------------------
    print(">>> Running Case 10: Zero-Consumption Party Member (Kavita)...")
    img10 = generate_mock_receipt_bytes(
        restaurant_name="Tea Lounge",
        bill_number="EDGE-10",
        items=[
            {"name": "Masala Chai", "qty": 1, "unit_price": 120.0, "amount": 120.0},
            {"name": "Bun Maska", "qty": 1, "unit_price": 100.0, "amount": 100.0}
        ],
        subtotal=220.0,
        cgst=5.5,
        sgst=5.5,
        round_off=0.0,
        grand_total=231.0
    )
    desc10 = "Three of us: Rohan, Sneha, Kavita. Rohan had the Masala Chai, Sneha had the Bun Maska. Kavita joined us for company but didn't eat or drink anything. Rohan paid."
    res10 = run_pipeline(img10, desc10)
    results["Case 10"] = res10

    # -------------------------------------------------------------
    # CASE 11: High-Complexity Stress Feast (10 items, Multi-Tax, Discount, 6-Person Group)
    # -------------------------------------------------------------
    print(">>> Running Case 11: High-Complexity Stress Feast (10 Items, Multi-Tax, 6-Person Group)...")
    r6_img_path = ROOT_DIR / "tests" / "sample_receipts" / "R6.png"
    if r6_img_path.exists():
        with open(r6_img_path, "rb") as f:
            img11 = f.read()
    else:
        img11 = img10
    desc11 = (
        "Party of six: Vikram, Ananya, Kabir, Rhea, Siddharth, Tara. "
        "Vikram and Kabir shared the 3 pints of Craft IPA Beer. "
        "Ananya and Tara had the Fresh Mint Mojitos. "
        "Siddharth and Rhea shared the Smoked BBQ Pork Ribs and Crispy Calamari. "
        "All six of us shared the 2 Wood-Fired Truffle Pizzas, Loaded Nachos Supreme, and Mineral Water. "
        "Ananya had the Classic Caesar Salad. "
        "Rhea, Tara, and Vikram shared the 2 Belgian Chocolate Lava Cakes. "
        "Vikram paid the entire bill."
    )
    res11 = run_pipeline(img11, desc11)
    results["Case 11"] = res11

    # Save all results to disk for complete traceability
    results_path = ROOT_DIR / "tests" / "edge_case_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Results written to {results_path}")

    for case_name, res in results.items():
        print(f"\n==================== {case_name} ====================")
        print(json.dumps(res, indent=2))

    return results


if __name__ == "__main__":
    run_all_edge_case_tests()

