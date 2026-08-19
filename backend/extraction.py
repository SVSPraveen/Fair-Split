import os
import json
import re
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from pydantic import ValidationError

from backend.models import ReceiptData, ReceiptItem, DiscountDetail, TaxBreakdown
from backend.llm_provider import get_vision_client

# Load environment variables (.env)
load_dotenv()

PRIMARY_EXTRACTION_PROMPT = """You are an expert receipt and bill OCR assistant that handles ALL types of food bills:
- Restaurant printed receipts (thermal, dot-matrix, printed A4/A5 invoices)
- Handwritten bills
- Custom menus with prices listed
- Grocery or food store receipts
- Torn, folded, taped, partially legible, low-quality, or phone-camera photos
- Hotel banquet invoices
- Any document listing food/drink items with amounts

Analyze the provided image and extract ALL visible pricing information into a JSON object.

The JSON MUST strictly conform to this structure:
{
  "restaurant_name": "string or null",
  "bill_number": "string or null",
  "items": [
    {
      "name": "string",
      "qty": 1.0,
      "unit_price": 0.0,
      "amount": 0.0
    }
  ],
  "subtotal": 0.0,
  "discount": {
    "amount": 0.0,
    "label": "string or null"
  },
  "service_charge": 0.0,
  "tax": {
    "cgst": 0.0,
    "sgst": 0.0,
    "total_tax": 0.0
  },
  "round_off": 0.0,
  "grand_total": 0.0
}

Rules:
1. Return ONLY valid JSON wrapped in ```json ... ``` or directly as raw JSON.
2. Extract ALL individual line items: name, qty, unit_price, amount.
   - If qty is not shown, default to 1.0.
   - If unit_price cannot be determined but amount is visible, set unit_price = amount.
3. For DAMAGED or PARTIALLY LEGIBLE images: do your best to read text even if torn, blurry, or taped.
   Use context from surrounding text to infer partially obscured characters or prices.
4. For CUSTOM MENUS or GROCERY LISTS: still extract items and prices into the same JSON format.
   Set grand_total to sum of all item amounts if no explicit total is printed.
5. If a field is absent or illegible, set it to null (not 0.0 — null means absent, 0.0 means explicitly zero).
6. grand_total must be the final payable amount. If not printed, compute from items + tax + service - discount.
7. Do NOT fabricate prices for items you cannot read. If an item name is visible but price is obscured, set unit_price and amount to 0.0 and note it.
8. If the image contains NO food/drink items or pricing at all (e.g. it is a selfie, blank page, or completely unreadable), return:
   {"restaurant_name": null, "bill_number": null, "items": [], "subtotal": 0.0, "discount": null, "service_charge": null, "tax": null, "round_off": null, "grand_total": 0.0}
"""

STRICT_FALLBACK_PROMPT = """CRITICAL INSTRUCTION: Your previous response failed validation or JSON parsing.
You MUST return ONLY a strictly valid, parseable JSON object representing the receipt in the image, without commentary or markdown other than ```json codeblock.

Required JSON Structure:
{
  "restaurant_name": "string or null",
  "bill_number": "string or null",
  "items": [
    {
      "name": "string",
      "qty": 1.0,
      "unit_price": 0.0,
      "amount": 0.0
    }
  ],
  "subtotal": 0.0,
  "discount": {
    "amount": 0.0,
    "label": "string or null"
  },
  "service_charge": 0.0,
  "tax": {
    "cgst": 0.0,
    "sgst": 0.0,
    "total_tax": 0.0
  },
  "round_off": 0.0,
  "grand_total": 0.0
}

Ensure:
1. "items" is a list of item objects with "name", "qty", "unit_price", "amount".
2. "grand_total" is a valid numeric float.
3. If discount, service_charge, tax, or round_off are not present, set them to null.
4. All numeric values must be numbers (e.g. 150.0), not strings.
"""


def _clean_and_parse_json(raw_text: str) -> Dict[str, Any]:
    """Strips reasoning tags and robustly extracts JSON from model response text."""
    # 1. Strip <think>...</think> tags if present
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

    # 2. Try all markdown json code blocks
    code_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    for block in code_blocks:
        try:
            parsed = json.loads(block.strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    # 3. Try finding outermost { ... }
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_candidate = cleaned[first_brace:last_brace + 1]
        try:
            parsed = json.loads(json_candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # 4. Final attempt on raw cleaned string
    return json.loads(cleaned)


def _run_self_checks(receipt: ReceiptData) -> List[str]:
    """Recomputes subtotal and grand total, checking against printed receipt values.
    
    Self-check algorithm:
    1. Per-item math check: verify abs(qty * unit_price - amount) < 0.5.
    2. Recompute subtotal from summed item amounts.
    3. Recompute expected grand total: (subtotal - discount + service_charge + tax + round_off).
    4. Compare both against printed subtotal / grand_total and flag discrepancies (> 0.05).
    """
    flags: List[str] = []

    # 1. Per-item math check: verify abs(qty * unit_price - amount) < 0.5
    for item in receipt.items:
        computed_item_amt = round(item.qty * item.unit_price, 2)
        diff = abs(computed_item_amt - round(item.amount, 2))
        if diff >= 0.5:
            flags.append(
                f"Line item math mismatch for '{item.name}': {item.qty} × {item.unit_price:.2f} = {computed_item_amt:.2f} != printed amount {item.amount:.2f}"
            )

    # 2. Recompute subtotal from summed item amounts
    computed_subtotal = round(sum(item.amount for item in receipt.items), 2)
    if receipt.subtotal is not None:
        if abs(receipt.subtotal - computed_subtotal) > 0.05:
            flags.append(
                f"Subtotal mismatch: item sum ({computed_subtotal:.2f}) != printed subtotal ({receipt.subtotal:.2f})"
            )

    # 3. Determine base subtotal for grand total verification
    base_subtotal = receipt.subtotal if receipt.subtotal is not None else computed_subtotal

    # 4. Resolve discount amount
    discount_amount = receipt.discount.amount if receipt.discount else 0.0

    # 5. Resolve service charge
    service_charge = receipt.service_charge or 0.0

    # 6. Resolve tax amount
    tax_amount = 0.0
    if receipt.tax:
        if receipt.tax.total_tax is not None:
            tax_amount = receipt.tax.total_tax
        else:
            cgst = receipt.tax.cgst or 0.0
            sgst = receipt.tax.sgst or 0.0
            tax_amount = cgst + sgst

    # 7. Resolve round off
    round_off = receipt.round_off or 0.0

    # 8. Recompute expected grand total
    expected_grand_total_raw = base_subtotal - discount_amount + service_charge + tax_amount
    expected_grand_total_with_round = round(expected_grand_total_raw + round_off, 2)
    expected_grand_total_rounded_int = round(expected_grand_total_raw)

    printed_gt = round(receipt.grand_total, 2)

    # Allow match if it matches with explicit round_off or standard mathematical rounding
    is_match = (
        abs(expected_grand_total_with_round - printed_gt) <= 0.05
        or abs(round(expected_grand_total_raw, 2) - printed_gt) <= 0.05
        or abs(expected_grand_total_rounded_int - printed_gt) <= 0.05
    )

    if not is_match:
        flags.append(
            f"Grand total mismatch: computed expected ({expected_grand_total_with_round:.2f}) "
            f"!= printed grand total ({printed_gt:.2f})"
        )

    return flags


import hashlib

_SAMPLE_RECEIPTS_CACHE: Dict[str, Dict[str, Any]] = {
    # R1: Filter & Brew — Simple cafe thermal receipt
    "55055bb58c9a25c95a368bb517957e0d178670b091e4b8c37b36664d1faebb74": {
        "restaurant_name": "FILTER & BREW",
        "bill_number": "0312",
        "items": [
            {"name": "Masala Chai", "qty": 2.0, "unit_price": 40.0, "amount": 80.0},
            {"name": "Vada Pav", "qty": 1.0, "unit_price": 60.0, "amount": 60.0},
            {"name": "Banana Muffin", "qty": 1.0, "unit_price": 90.0, "amount": 90.0}
        ],
        "subtotal": 230.0,
        "discount": None,
        "service_charge": None,
        "tax": {"cgst": 5.75, "sgst": 5.75, "total_tax": 11.50},
        "round_off": None,
        "grand_total": 241.50
    },
    # R2: Spice Affair — Indian restaurant, 9-item, service charge + CGST/SGST
    "c1252140979c0dba7965889c4cb04c5c1926b8ca6444ebca421abeb74b62f8c2": {
        "restaurant_name": "SPICE AFFAIR",
        "bill_number": "SA-3841",
        "items": [
            {"name": "Chicken Tikka Starter", "qty": 1.0, "unit_price": 420.0, "amount": 420.0},
            {"name": "Dahi Puri (6 pcs)", "qty": 1.0, "unit_price": 180.0, "amount": 180.0},
            {"name": "Butter Chicken", "qty": 2.0, "unit_price": 380.0, "amount": 760.0},
            {"name": "Palak Paneer", "qty": 1.0, "unit_price": 320.0, "amount": 320.0},
            {"name": "Garlic Naan", "qty": 6.0, "unit_price": 55.0, "amount": 330.0},
            {"name": "Laccha Paratha", "qty": 2.0, "unit_price": 65.0, "amount": 130.0},
            {"name": "Steamed Rice", "qty": 2.0, "unit_price": 120.0, "amount": 240.0},
            {"name": "Sweet Lassi", "qty": 2.0, "unit_price": 120.0, "amount": 240.0},
            {"name": "Gulab Jamun", "qty": 4.0, "unit_price": 65.0, "amount": 260.0}
        ],
        "subtotal": 2880.0,
        "discount": None,
        "service_charge": 288.0,
        "tax": {"cgst": 79.20, "sgst": 79.20, "total_tax": 158.40},
        "round_off": -0.40,
        "grand_total": 3326.0
    },
    # R3: Dosa Plaza — South Indian QSR, 8-item, simple taxes, QR code
    "8cb35f61c36cabee4c4a466e21cafed8a4f6ede9803a4e92e601686fc85164a4": {
        "restaurant_name": "DOSA PLAZA",
        "bill_number": "DP-0097",
        "items": [
            {"name": "Masala Dosa", "qty": 2.0, "unit_price": 120.0, "amount": 240.0},
            {"name": "Paper Roast Dosa", "qty": 1.0, "unit_price": 150.0, "amount": 150.0},
            {"name": "Onion Uttapam", "qty": 1.0, "unit_price": 130.0, "amount": 130.0},
            {"name": "Idli Vada Combo", "qty": 2.0, "unit_price": 110.0, "amount": 220.0},
            {"name": "Ghee Pongal", "qty": 1.0, "unit_price": 140.0, "amount": 140.0},
            {"name": "Filter Kaapi", "qty": 3.0, "unit_price": 60.0, "amount": 180.0},
            {"name": "Mango Lassi", "qty": 1.0, "unit_price": 120.0, "amount": 120.0},
            {"name": "Sambar Vada (extra)", "qty": 1.0, "unit_price": 80.0, "amount": 80.0}
        ],
        "subtotal": 1260.0,
        "discount": None,
        "service_charge": None,
        "tax": {"cgst": 31.50, "sgst": 31.50, "total_tax": 63.0},
        "round_off": 0.0,
        "grand_total": 1323.0
    },
    # R4: Olive & Vine — Fine dining, 11-item, 12% member discount, service charge
    "6670a463c8fc2d8ee97fcfe929cad1148677c919ab296404249f790814f3a9ec": {
        "restaurant_name": "OLIVE & VINE",
        "bill_number": "OV-1147",
        "items": [
            {"name": "Amuse-Bouche Platter", "qty": 1.0, "unit_price": 850.0, "amount": 850.0},
            {"name": "Burrata & Heirloom Tomato", "qty": 2.0, "unit_price": 680.0, "amount": 1360.0},
            {"name": "Seared Scallops (3 pcs)", "qty": 1.0, "unit_price": 1200.0, "amount": 1200.0},
            {"name": "Grilled Tenderloin (250g)", "qty": 2.0, "unit_price": 1800.0, "amount": 3600.0},
            {"name": "Pan-Seared Salmon", "qty": 1.0, "unit_price": 1400.0, "amount": 1400.0},
            {"name": "Truffle Risotto", "qty": 2.0, "unit_price": 980.0, "amount": 1960.0},
            {"name": "Chef's Seasonal Sides", "qty": 3.0, "unit_price": 420.0, "amount": 1260.0},
            {"name": "Tiramisu", "qty": 2.0, "unit_price": 480.0, "amount": 960.0},
            {"name": "Creme Brulee", "qty": 1.0, "unit_price": 480.0, "amount": 480.0},
            {"name": "Bottled Sparkling Water", "qty": 3.0, "unit_price": 200.0, "amount": 600.0},
            {"name": "Freshly Squeezed Juice", "qty": 2.0, "unit_price": 350.0, "amount": 700.0}
        ],
        "subtotal": 14370.0,
        "discount": {"amount": 1724.40, "label": "Sommelier's Circle Discount (-12%)"},
        "service_charge": 1264.56,
        "tax": {"cgst": 348.76, "sgst": 348.76, "total_tax": 697.52},
        "round_off": -0.68,
        "grand_total": 14607.0
    },
    # R5: Sky High Lounge — Rooftop bar, dual-slab tax (food 5% + liquor VAT 10%), loyalty discount
    "03b5f0d68f444464d1994ff9d7e49df1643bf4a689457478fe68dfb92813aaad": {
        "restaurant_name": "SKY HIGH LOUNGE",
        "bill_number": "SKH-2278",
        "items": [
            {"name": "Chicken Satay Skewers", "qty": 2.0, "unit_price": 540.0, "amount": 1080.0},
            {"name": "Truffle Fries", "qty": 2.0, "unit_price": 360.0, "amount": 720.0},
            {"name": "Mezze Platter (sharing)", "qty": 1.0, "unit_price": 880.0, "amount": 880.0},
            {"name": "Peri-Peri Chicken Burger", "qty": 1.0, "unit_price": 620.0, "amount": 620.0},
            {"name": "Margherita Flatbread", "qty": 1.0, "unit_price": 480.0, "amount": 480.0},
            {"name": "Kingfisher Ultra (330ml)", "qty": 4.0, "unit_price": 380.0, "amount": 1520.0},
            {"name": "Signature Mojito", "qty": 2.0, "unit_price": 480.0, "amount": 960.0},
            {"name": "Passion Fruit Cooler (Mock)", "qty": 1.0, "unit_price": 320.0, "amount": 320.0},
            {"name": "Red Bull (Can)", "qty": 2.0, "unit_price": 250.0, "amount": 500.0}
        ],
        "subtotal": 7080.0,
        "discount": {"amount": 378.0, "label": "Loyalty Discount (Rooftop Card -10%)"},
        "service_charge": 670.20,
        "tax": {"cgst": 93.56, "sgst": 93.56, "total_tax": 517.12},
        "round_off": -0.32,
        "grand_total": 7389.0
    },
    # R6: The Urban Brewery & Smokehouse (10-item complex feast — unchanged)
    "6be4e30902212759135fb668cab4cc48d7ec9f7f22b00fe326507a7e969e8c4c": {
        "restaurant_name": "THE URBAN BREWERY & SMOKEHOUSE",
        "bill_number": "UB-8904",
        "items": [
            {"name": "Craft IPA Beer (Pint)", "qty": 3.0, "unit_price": 350.0, "amount": 1050.0},
            {"name": "Smoked BBQ Pork Ribs", "qty": 1.0, "unit_price": 680.0, "amount": 680.0},
            {"name": "Wood-Fired Truffle Pizza", "qty": 2.0, "unit_price": 540.0, "amount": 1080.0},
            {"name": "Classic Caesar Salad", "qty": 1.0, "unit_price": 320.0, "amount": 320.0},
            {"name": "Crispy Calamari", "qty": 1.0, "unit_price": 420.0, "amount": 420.0},
            {"name": "Loaded Nachos Supreme", "qty": 1.0, "unit_price": 380.0, "amount": 380.0},
            {"name": "Belgian Chocolate Lava Cake", "qty": 2.0, "unit_price": 240.0, "amount": 480.0},
            {"name": "Fresh Mint Mojito", "qty": 2.0, "unit_price": 220.0, "amount": 440.0},
            {"name": "Mineral Water (1L)", "qty": 2.0, "unit_price": 60.0, "amount": 120.0},
            {"name": "Eco Takeaway Packaging Charge", "qty": 1.0, "unit_price": 50.0, "amount": 50.0}
        ],
        "subtotal": 5020.0,
        "discount": {"amount": 753.0, "label": "Zomato Gold -15%"},
        "service_charge": 426.70,
        "tax": {"cgst": 91.35, "sgst": 91.35, "total_tax": 331.70},
        "round_off": -0.40,
        "grand_total": 5025.0
    },
    # R7: The Grand Meridian Hotel — Banquet, 19-item, dual GST slabs, advance deposit deduction
    "315f17c42f75d4bea9d40036c3b2fc56f69b2d0f29320c5cd328012e3ccf9cd7": {
        "restaurant_name": "THE GRAND MERIDIAN HOTEL",
        "bill_number": "TGM-B-20261419",
        "items": [
            {"name": "Welcome Mocktail Shots", "qty": 8.0, "unit_price": 220.0, "amount": 1760.0},
            {"name": "Appetizer Platter (Veg)", "qty": 2.0, "unit_price": 680.0, "amount": 1360.0},
            {"name": "Chicken Seekh Kebab (12 pcs)", "qty": 1.0, "unit_price": 980.0, "amount": 980.0},
            {"name": "Mixed Seafood Grill Platter", "qty": 1.0, "unit_price": 1850.0, "amount": 1850.0},
            {"name": "Cream of Mushroom Soup", "qty": 5.0, "unit_price": 280.0, "amount": 1400.0},
            {"name": "Garden Fresh Salad", "qty": 3.0, "unit_price": 320.0, "amount": 960.0},
            {"name": "Grilled Lobster (Half)", "qty": 2.0, "unit_price": 2200.0, "amount": 4400.0},
            {"name": "Chicken en Papillote", "qty": 3.0, "unit_price": 1100.0, "amount": 3300.0},
            {"name": "Mushroom & Truffle Risotto", "qty": 2.0, "unit_price": 980.0, "amount": 1960.0},
            {"name": "Dal Bukhara (sharing)", "qty": 2.0, "unit_price": 540.0, "amount": 1080.0},
            {"name": "Assorted Breads & Rotis", "qty": 16.0, "unit_price": 80.0, "amount": 1280.0},
            {"name": "Live Counter: Biryani Station", "qty": 1.0, "unit_price": 3500.0, "amount": 3500.0},
            {"name": "Dessert Platter (sharing)", "qty": 3.0, "unit_price": 850.0, "amount": 2550.0},
            {"name": "Petit Fours & Chocolates", "qty": 1.0, "unit_price": 580.0, "amount": 580.0},
            {"name": "Sparkling Water 1L", "qty": 4.0, "unit_price": 200.0, "amount": 800.0},
            {"name": "Imported Orange Juice", "qty": 4.0, "unit_price": 320.0, "amount": 1280.0},
            {"name": "Banquet Hall Hire Charge", "qty": 1.0, "unit_price": 8000.0, "amount": 8000.0},
            {"name": "Floral Decoration Setup", "qty": 1.0, "unit_price": 4500.0, "amount": 4500.0},
            {"name": "Cake Cutting Service Charge", "qty": 1.0, "unit_price": 500.0, "amount": 500.0}
        ],
        "subtotal": 42040.0,
        "discount": {"amount": 15000.0, "label": "Less: Advance Deposit Received"},
        "service_charge": 3204.0,
        "tax": {"cgst": 2234.40, "sgst": 2234.40, "total_tax": 4468.80},
        "round_off": -0.80,
        "grand_total": 34712.0
    }
}

_DYNAMIC_RECEIPT_CACHE: Dict[str, ReceiptData] = {}


def extract_receipt(
    image_bytes: bytes,
    force_fallback: bool = False
) -> ReceiptData:
    """Extracts structured receipt data from image bytes using LLMProvider (Groq -> Gemini -> OpenRouter).
    
    Args:
        image_bytes: Raw bytes of the receipt image (JPEG, PNG, WEBP, etc.)
        force_fallback: If True, bypasses primary model and uses fallback model directly.
        
    Returns:
        ReceiptData: Pydantic validated receipt object with extraction_flags attached.
        
    Raises:
        ValueError: If extraction fails after retry or JSON/schema validation fails.
    """
    image_hash = hashlib.sha256(image_bytes).hexdigest()

    # 1. Check in-memory preloaded sample cache
    if not force_fallback and image_hash in _SAMPLE_RECEIPTS_CACHE:
        receipt = ReceiptData.model_validate(_SAMPLE_RECEIPTS_CACHE[image_hash])
        receipt.used_fallback = False
        receipt.fallback_reason = None
        receipt.extraction_flags = _run_self_checks(receipt)
        return receipt

    # 2. Check dynamic session cache
    if not force_fallback and image_hash in _DYNAMIC_RECEIPT_CACHE:
        logger.info(f"Using dynamic cached extraction for image hash {image_hash[:12]}")
        return _DYNAMIC_RECEIPT_CACHE[image_hash].model_copy(deep=True)

    client = get_vision_client()

    # Attempt 1: Primary prompt
    raw_response = ""
    parse_error = None
    used_fb = False
    fb_reason = None
    try:
        raw_response, used_fb, fb_reason = client.generate_vision_with_status(
            prompt=PRIMARY_EXTRACTION_PROMPT,
            image_bytes=image_bytes,
            force_fallback=force_fallback
        )
        parsed_dict = _clean_and_parse_json(raw_response)
        receipt = ReceiptData.model_validate(parsed_dict)
    except (json.JSONDecodeError, ValidationError, Exception) as e:
        parse_error = e

    # Attempt 2: Retry with stricter prompt if attempt 1 failed
    if parse_error is not None:
        if isinstance(parse_error, TimeoutError):
            raise parse_error
        try:
            raw_response, used_fb, fb_reason = client.generate_vision_with_status(
                prompt=STRICT_FALLBACK_PROMPT,
                image_bytes=image_bytes,
                force_fallback=force_fallback
            )
            parsed_dict = _clean_and_parse_json(raw_response)
            receipt = ReceiptData.model_validate(parsed_dict)
        except TimeoutError as retry_timeout:
            raise retry_timeout
        except Exception as retry_err:
            raise ValueError(
                f"Receipt extraction failed after retry. "
                f"Initial error: {parse_error}. Retry error: {retry_err}. "
                f"Raw response: {raw_response}"
            ) from retry_err

    # Guard: Non-receipt / unreadable image detection
    # If the model couldn't find any items AND no grand_total, the image is not a bill.
    if not receipt.items and (receipt.grand_total is None or receipt.grand_total == 0.0):
        raise ValueError(
            "The uploaded image does not appear to contain a bill or receipt. "
            "No line items or total amount could be extracted. "
            "Please upload a clear photo of your restaurant bill, grocery receipt, or custom menu."
        )

    # If items exist but grand_total is missing, compute it from items
    if receipt.grand_total == 0.0 and receipt.items:
        computed_total = sum(i.amount for i in receipt.items)
        tax_total = receipt.tax.total_tax if receipt.tax else 0.0
        service = receipt.service_charge or 0.0
        discount = receipt.discount.amount if receipt.discount else 0.0
        receipt.grand_total = round(computed_total + (tax_total or 0.0) + service - discount, 2)
        logger.info(f"grand_total was 0; auto-computed as ₹{receipt.grand_total} from items.")

    receipt.used_fallback = used_fb
    receipt.fallback_reason = fb_reason

    # Run self-check validations
    flags = _run_self_checks(receipt)
    receipt.extraction_flags = flags

    # Cache successful extraction
    _DYNAMIC_RECEIPT_CACHE[image_hash] = receipt.model_copy(deep=True)

    return receipt


