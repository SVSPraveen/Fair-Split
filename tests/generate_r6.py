import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT_DIR / "tests" / "sample_receipts" / "R6.png"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


def generate_hard_complex_receipt():
    # Width and height for realistic thermal receipt
    width = 600
    height = 960

    # Clean off-white paper texture background
    img = Image.new("RGB", (width, height), color=(252, 252, 250))
    draw = ImageDraw.Draw(img)

    # Try loading fonts or fallback to default
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 22)
        font_header = ImageFont.truetype("arial.ttf", 13)
        font_bold = ImageFont.truetype("arialbd.ttf", 14)
        font_regular = ImageFont.truetype("arial.ttf", 13)
        font_mono = ImageFont.truetype("consola.ttf", 13)
        font_mono_bold = ImageFont.truetype("consolab.ttf", 14)
        font_small = ImageFont.truetype("arial.ttf", 11)
    except Exception:
        font_title = font_header = font_bold = font_regular = font_mono = font_mono_bold = font_small = ImageFont.load_default()

    y = 25

    # Header & Restaurant Info
    draw.text((width // 2, y), "THE URBAN BREWERY & SMOKEHOUSE", fill=(20, 20, 20), font=font_title, anchor="mt")
    y += 28
    draw.text((width // 2, y), "100ft Road, Indiranagar, Bengaluru - 560038", fill=(70, 70, 70), font=font_header, anchor="mt")
    y += 18
    draw.text((width // 2, y), "GSTIN: 29AABCU9603R1ZX | FSSAI: 11219333000542", fill=(90, 90, 90), font=font_small, anchor="mt")
    y += 22

    # Divider
    draw.line([(30, y), (width - 30, y)], fill=(180, 180, 180), width=1)
    y += 10

    # Meta
    draw.text((35, y), "Table: T-14 (Rooftop)", fill=(40, 40, 40), font=font_bold)
    draw.text((width - 35, y), "Bill No: UB-8904", fill=(40, 40, 40), font=font_bold, anchor="rt")
    y += 18
    draw.text((35, y), "Date: 18-Aug-2026 21:45", fill=(80, 80, 80), font=font_small)
    draw.text((width - 35, y), "Server: Rajesh K. | Covers: 6", fill=(80, 80, 80), font=font_small, anchor="rt")
    y += 22

    # Table Header
    draw.line([(30, y), (width - 30, y)], fill=(120, 120, 120), width=1)
    y += 6
    draw.text((35, y), "ITEM DESCRIPTION", fill=(50, 50, 50), font=font_bold)
    draw.text((360, y), "QTY", fill=(50, 50, 50), font=font_bold)
    draw.text((430, y), "RATE", fill=(50, 50, 50), font=font_bold)
    draw.text((width - 35, y), "AMOUNT", fill=(50, 50, 50), font=font_bold, anchor="rt")
    y += 20
    draw.line([(30, y), (width - 30, y)], fill=(180, 180, 180), width=1)
    y += 10

    # Items (10 Items)
    items = [
        ("Craft IPA Beer (Pint)", 3, 350.00, 1050.00),
        ("Smoked BBQ Pork Ribs", 1, 680.00, 680.00),
        ("Wood-Fired Truffle Pizza", 2, 540.00, 1080.00),
        ("Classic Caesar Salad", 1, 320.00, 320.00),
        ("Crispy Calamari", 1, 420.00, 420.00),
        ("Loaded Nachos Supreme", 1, 380.00, 380.00),
        ("Belgian Chocolate Lava Cake", 2, 240.00, 480.00),
        ("Fresh Mint Mojito", 2, 220.00, 440.00),
        ("Mineral Water (1L)", 2, 60.00, 120.00),
        ("Eco Takeaway Packaging Charge", 1, 50.00, 50.00),
    ]

    for name, qty, rate, amt in items:
        draw.text((35, y), name, fill=(20, 20, 20), font=font_regular)
        draw.text((370, y), str(qty), fill=(20, 20, 20), font=font_mono)
        draw.text((430, y), f"{rate:.2f}", fill=(20, 20, 20), font=font_mono)
        draw.text((width - 35, y), f"{amt:.2f}", fill=(20, 20, 20), font=font_mono_bold, anchor="rt")
        y += 22

    y += 6
    draw.line([(30, y), (width - 30, y)], fill=(180, 180, 180), width=1)
    y += 12

    # Calculations Summary
    summary_lines = [
        ("Item Subtotal", "5020.00", False),
        ("Discount (Zomato Gold -15%)", "-753.00", False),
        ("Net Food & Beverage Subtotal", "4267.00", True),
        ("Service Charge (10%)", "426.70", False),
        ("CGST @ 2.5% (Food)", "91.35", False),
        ("SGST @ 2.5% (Food)", "91.35", False),
        ("State Liquor VAT @ 10% (Beverages)", "149.00", False),
        ("Total Taxes & Levies", "331.70", False),
        ("Round Off Adjustment", "-0.40", False),
    ]

    for label, val, is_bold in summary_lines:
        f = font_bold if is_bold else font_regular
        f_val = font_mono_bold if is_bold else font_mono
        color = (180, 20, 20) if "-" in val else (20, 20, 20)
        draw.text((220, y), label, fill=(50, 50, 50), font=f)
        draw.text((width - 35, y), val, fill=color, font=f_val, anchor="rt")
        y += 20

    y += 8
    draw.line([(30, y), (width - 30, y)], fill=(40, 40, 40), width=2)
    y += 12

    # Grand Total Box
    draw.rectangle([(30, y), (width - 30, y + 42)], fill=(240, 245, 255), outline=(37, 99, 235), width=2)
    draw.text((45, y + 10), "FINAL GRAND TOTAL", fill=(15, 23, 42), font=font_title)
    draw.text((width - 45, y + 8), "₹ 5,025.00", fill=(37, 99, 235), font=font_title, anchor="rt")
    y += 56

    # Footer
    draw.text((width // 2, y), "Thank you for dining at The Urban Brewery!", fill=(80, 80, 80), font=font_header, anchor="mt")
    y += 18
    draw.text((width // 2, y), "Please tip your server • Service Charge is discretionary", fill=(110, 110, 110), font=font_small, anchor="mt")

    img.save(OUTPUT_PATH, "PNG")
    print(f"Generated R6 Hard Complex Receipt at: {OUTPUT_PATH}")


if __name__ == "__main__":
    generate_hard_complex_receipt()
