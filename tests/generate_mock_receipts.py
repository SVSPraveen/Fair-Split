import os
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "sample_receipts")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_font(size: int = 18):
    """Attempt to load a standard monospace font, fallback to default."""
    try:
        return ImageFont.truetype("consola.ttf", size)
    except IOError:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except IOError:
            return ImageFont.load_default()


def render_receipt_image(filename: str, lines: list, width: int = 550, line_height: int = 24):
    """Renders formatted text lines onto a receipt-style canvas."""
    font = get_font(18)
    title_font = get_font(22)
    
    height = len(lines) * line_height + 80
    img = Image.new("RGB", (width, height), color="#FAF9F6")
    draw = ImageDraw.Draw(img)

    # Draw a slight border / receipt outline
    draw.rectangle([(5, 5), (width - 6, height - 6)], outline="#D0D0D0", width=2)
    
    y = 25
    for line in lines:
        is_title = line.startswith("===") or line.startswith("***")
        f = title_font if is_title else font
        fill_color = "#111111"
        
        # Center title-like headers
        if is_title or line.startswith("   "):
            draw.text((25, y), line, fill=fill_color, font=f)
        else:
            draw.text((30, y), line, fill=fill_color, font=f)
        y += line_height

    filepath = os.path.join(OUTPUT_DIR, filename)
    img.save(filepath, "PNG")
    print(f"Generated mock receipt: {filepath}")


def generate_r1():
    """R1 — Brew & Bite Café, Koramangala, Bengaluru, Bill #0142"""
    lines = [
        "*** BREW & BITE CAFE ***",
        "    Artisan Coffee & Eatery    ",
        "  Koramangala, Bengaluru - 560034 ",
        "Date: 18-Aug-2026  Time: 12:45",
        "Bill No: 0142      Table: C-03",
        "----------------------------------------",
        "ITEM                  QTY  PRICE  AMOUNT",
        "----------------------------------------",
        "Cappuccino            1.0 180.00  180.00",
        "Grilled Chicken Sandwich 1.0 260.00 260.00",
        "Penne Arrabiata       1.0 320.00  320.00",
        "Fresh Lime Soda       1.0 120.00  120.00",
        "Brownie               1.0 160.00  160.00",
        "----------------------------------------",
        "Subtotal:                       1,040.00",
        "Service Charge (5%):               52.00",
        "CGST (2.5%):                       27.30",
        "SGST (2.5%):                       27.30",
        "Round Off:                          0.40",
        "----------------------------------------",
        "GRAND TOTAL:                    1,147.00",
        "========================================",
        "      Thank you for dining!      ",
    ]
    render_receipt_image("R1.png", lines)


def generate_r2():
    """R2 — Tamarind Kitchen, HSR Layout, Bengaluru, Bill #2207"""
    lines = [
        "*** TAMARIND KITCHEN ***",
        "     Traditional Dining        ",
        "  HSR Layout, Bengaluru - 560102 ",
        "Date: 18-Aug-2026  Time: 20:30",
        "Bill No: 2207      Table: T-04",
        "----------------------------------------",
        "ITEM                  QTY  PRICE  AMOUNT",
        "----------------------------------------",
        "Paneer Butter Masala  1.0 320.00  320.00",
        "Dal Makhani           1.0 260.00  260.00",
        "Butter Naan           4.0  60.00  240.00",
        "Jeera Rice            1.0 180.00  180.00",
        "Gulab Jamun           2.0  60.00  120.00",
        "Masala Papad          2.0  50.00  100.00",
        "----------------------------------------",
        "Subtotal:                       1,220.00",
        "Service Charge (5%):               61.00",
        "CGST (2.5%):                       32.03",
        "SGST (2.5%):                       32.02",
        "Round Off:                         -0.05",
        "----------------------------------------",
        "GRAND TOTAL:                    1,345.00",
        "========================================",
        "       Have a Wonderful Night!    ",
    ]
    render_receipt_image("R2.png", lines)


def generate_r3():
    """R3 — The Daily Grind, Powai, Mumbai, Bill #1188"""
    lines = [
        "*** THE DAILY GRIND ***",
        "  Cafe, Bar & Italian Kitchen   ",
        "  Powai, Mumbai - 400076        ",
        "Date: 18-Aug-2026  Time: 21:15",
        "Bill No: 1188      Table: T-12",
        "----------------------------------------",
        "ITEM                  QTY  PRICE  AMOUNT",
        "----------------------------------------",
        "Margherita Pizza      1.0 380.00  380.00",
        "Arrabiata Pasta       1.0 340.00  340.00",
        "Garlic Bread          1.0 160.00  160.00",
        "Craft Beer            2.0 250.00  500.00",
        "Virgin Mojito         1.0 180.00  180.00",
        "----------------------------------------",
        "Subtotal:                       1,560.00",
        "Service Charge (5%):               78.00",
        "CGST (2.5%):                       40.95",
        "SGST (2.5%):                       40.95",
        "Round Off:                          0.10",
        "----------------------------------------",
        "GRAND TOTAL:                    1,720.00",
        "========================================",
        "      Buon Appetito & Cheers!    ",
    ]
    render_receipt_image("R3.png", lines)


def generate_r4():
    """R4 — Spice Route, Jubilee Hills, Hyderabad, Bill #5521"""
    lines = [
        "*** SPICE ROUTE ***",
        "    Mughlai & Biryani Dining    ",
        "  Jubilee Hills, Hyderabad - 500033",
        "Date: 18-Aug-2026  Time: 22:10  ",
        "Bill No: 5521      Table: D-01  ",
        "----------------------------------------",
        "ITEM                  QTY  PRICE  AMOUNT",
        "----------------------------------------",
        "Chicken Biryani       2.0 280.00  560.00",
        "Veg Biryani           1.0 240.00  240.00",
        "Mutton Rogan Josh     1.0 420.00  420.00",
        "Raita                 2.0  60.00  120.00",
        "Soft Drinks           3.0  60.00  180.00",
        "----------------------------------------",
        "Subtotal:                       1,520.00",
        "Discount (WELCOME15 -15%):      -228.00",
        "Service Charge (5%):               76.00",
        "CGST (2.5%):                       34.20",
        "SGST (2.5%):                       34.20",
        "Round Off:                         -0.40",
        "----------------------------------------",
        "GRAND TOTAL:                    1,436.00",
        "========================================",
        "          Shukriya, Visit Again! ",
    ]
    render_receipt_image("R4.png", lines)


def generate_r5():
    """Generates R5 with an intentional 20-rupee gap between line items (980) and printed subtotal (1000)."""
    lines = [
        "*** THE IRREGULAR CAFE ***",
        "     Bakes & Bites Lounge      ",
        "  10 Church Street, Bangalore  ",
        "Date: 18-Aug-2026  Time: 19:45 ",
        "Bill No: IRR-505   Table: T-07 ",
        "----------------------------------------",
        "ITEM                  QTY  PRICE  AMOUNT",
        "----------------------------------------",
        "Margherita Pizza      1.0 400.00  400.00",
        "Garlic Bread          1.0 180.00  180.00",
        "Cold Coffee           2.0 200.00  400.00",
        "----------------------------------------",
        "Subtotal:                       1,000.00",
        "CGST (2.5%):                       25.00",
        "SGST (2.5%):                       25.00",
        "----------------------------------------",
        "GRAND TOTAL:                    1,050.00",
        "========================================",
        "        Have a Pleasant Day!    ",
    ]
    render_receipt_image("R5.png", lines)


if __name__ == "__main__":
    generate_r1()
    generate_r2()
    generate_r3()
    generate_r4()
    generate_r5()
    print("All 5 mock receipts (including ground-truth R1-R4 and mismatch R5) generated successfully.")
